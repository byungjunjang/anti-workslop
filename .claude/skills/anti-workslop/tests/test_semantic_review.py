import json
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_fidelity import load_pair, to_json, compare, summarize
from semantic_review import packet, review_status
from check_ai_tells import check, load_rules


class SemanticTests(unittest.TestCase):
    def pair(self, a, b):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p, q = Path(tmp.name)/'a.md', Path(tmp.name)/'b.md'
        p.write_text(a, encoding='utf-8'); q.write_text(b, encoding='utf-8')
        od, pd, mode = load_pair(str(p), str(q), 'auto', False)
        return od, pd, packet(od, pd)

    def test_drift_routes_without_claiming_error(self):
        for a, b in [
            ('서울 매출은 10억원이다. 부산 매출은 20억원이다.', '서울 매출은 20억원이다. 부산 매출은 10억원이다.'),
            ('다음 달 도입을 검토 중이다.', '다음 달 도입을 확정했다.'),
            ('서울은 지원하지 않는다. 부산은 지원한다.', '서울은 지원한다. 부산은 지원하지 않는다.')]:
            od, pd, data = self.pair(a, b)
            self.assertTrue(data['risks'])
            self.assertEqual(review_status(data)['status'], '확인 필요')
            findings, stats = compare(od, pd)
            self.assertFalse(summarize(findings)['strict_fail'])
            payload = to_json(findings, summarize(findings), stats, od, pd, 'md')
            self.assertIn('semantic_review', payload)
            self.assertIn('summary', payload)

    def test_moves_and_normal_edits(self):
        _, _, data = self.pair('서울은 10억원이다.\n\n부산은 지원하지 않는다.', '부산은 지원하지 않는다.\n\n서울은 10억원이다.')
        self.assertEqual(data['risks'], [])
        _, _, data = self.pair('책을 차근차근 읽는다.', '책을 천천히 읽는다.')
        self.assertEqual(data['risks'], [])
        od, pd, data = self.pair('금액은 1,000원이다.', '금액은 1000원이다.')
        self.assertFalse(summarize(compare(od, pd)[0])['strict_fail'])

    def test_add_delete_split_and_protected(self):
        # 분할·병합은 T1 이후 위험이 아니다(test_sentence_pairs_only_flag_differences 가 본다).
        for a,b in [('오늘 읽는다.', '오늘 읽는다.\n\n내일 쓴다.'), ('> 그는 읽는다.', '> 그는 쓴다.')]:
            _, _, data = self.pair(a,b)
            self.assertTrue(data['risks'])
            self.assertTrue(all(x and x['section_end'] >= x['line'] for r in data['risks'] for x in [r['orig'],r['polished']] if x))

    def test_sentence_pairs_only_flag_differences(self):
        # 같은 문장을 두 문단으로 나눈 것은 위험이 아니다(T1).
        _, _, data = self.pair('하나를 읽는다. 둘을 쓴다.', '하나를 읽는다.\n\n둘을 쓴다.')
        self.assertEqual(data['risks'], [])
        # 문장을 합친 것도 위험이 아니다.
        _, _, data = self.pair('하나를 읽는다.\n\n둘을 쓴다.', '하나를 읽는다. 둘을 쓴다.')
        self.assertEqual(data['risks'], [])
        # 표지가 없는 문장을 고쳐 쓴 것은 위험이 아니다(test_moves_and_normal_edits 가 본다).
        # 표지가 든 문장이 많이 달라지면 표지가 같아도 올린다(붙는 대상이 바뀌는 자리를
        # 코드가 가리지 못한다). 이 보수 규칙이 「서울→부산」 같은 옮겨감을 지킨다.
        _, _, data = self.pair('서울 매출은 10억원이다.', '매출은 서울에서 10억원이다.')
        self.assertEqual([r['reasons'] for r in data['risks']], [['표지가 있는 문장의 재작성']])
        _, _, data = self.pair('서울은 지원하지 않는다. 부산은 지원한다.',
                               '서울은 지원한다. 부산은 지원하지 않는다.')
        self.assertTrue(data['risks'])
        # 수치·부정·확정 수준이 달라지면 위험이다.
        for a, b in [('서울 매출은 10억원이다.', '서울 매출은 20억원이다.'),
                     ('서울은 지원하지 않는다.', '서울은 지원한다.'),
                     ('다음 달 도입을 검토 중이다.', '다음 달 도입을 확정했다.')]:
            _, _, data = self.pair(a, b)
            self.assertEqual(len(data['risks']), 1, (a, b, data['risks']))

    def test_unpaired_units_group_by_section(self):
        orig = '# 가\n\n하나를 읽는다.\n\n둘을 쓴다.\n\n# 나\n\n셋을 센다.\n'
        pol = '# 가\n\n넷을 굽는다.\n\n다섯을 접는다.\n\n# 나\n\n여섯을 던진다.\n'
        _, _, data = self.pair(orig, pol)
        self.assertEqual(len(data['risks']), 2, data['risks'])
        for r in data['risks']:
            self.assertIn('추가·삭제·대응 불명', r['reasons'])
            self.assertTrue(r['orig'] and r['polished'])

    def test_protected_blocks_still_compared_whole(self):
        _, _, data = self.pair('> 그는 읽는다.', '> 그는 쓴다.')
        self.assertTrue(data['risks'])
        self.assertIn('고정 구역 변경', data['risks'][0]['reasons'])

    def test_record_coverage_and_staleness(self):
        _, _, data = self.pair('서울 매출은 10억원이다.', '서울 매출은 20억원이다.')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'review.json'
            record={'schema_version':1, **{k:data[k] for k in ('orig_sha256','polished_sha256')}, 'independent':True, 'reviewer':'test reviewer',
                    'items':[{'id':r['id'],'verdict':'보존 확인','evidence':'합성 기록 검증용 근거'} for r in data['risks']]}
            def status():
                p.write_text(json.dumps(record),encoding='utf-8')
                return review_status(data,p)['status']
            self.assertEqual(status(),'독립 검토 완료')
            record['items'][0]['verdict']='판단 불가'; self.assertEqual(status(),'확인 필요')
            record['items'][0]['verdict']='의미 변경'; self.assertEqual(status(),'확인 필요')
            record['items'][0]['verdict']='보존 확인'
            record['polished_sha256']='stale'; self.assertEqual(status(),'확인 필요')
            record['polished_sha256']=data['polished_sha256']
            record['items']=[]; self.assertEqual(status(),'확인 필요')
            self.assertEqual(review_status({'risks':[]},concern=True)['status'],'확인 필요')

    def _record(self, data, **over):
        rec = {'schema_version': 2, 'orig_sha256': data['orig_sha256'],
               'polished_sha256': data['polished_sha256'], 'independent': True,
               'reviewer': 'test', 'method': 'llm',
               'preserved': [r['id'] for r in data['risks']], 'items': []}
        rec.update(over)
        return rec

    def test_record_v2_preserved_list(self):
        _, _, data = self.pair('서울 매출은 10억원이다.', '서울 매출은 20억원이다.')
        ids = [r['id'] for r in data['risks']]
        self.assertTrue(ids)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'r.json'

            def status(rec):
                p.write_text(json.dumps(rec, ensure_ascii=False), encoding='utf-8')
                return review_status(data, [p])

            self.assertEqual(status(self._record(data))['status'], '독립 검토 완료')
            self.assertEqual(status(self._record(data))['counts']['preserved'], len(ids))
            # 같은 ID 가 preserved 와 items 에 겹치면 안 된다
            bad = self._record(data, items=[{'id': ids[0], 'verdict': '의미 변경', 'evidence': '값이 다르다'}])
            self.assertEqual(status(bad)['status'], '확인 필요')
            # 하나를 items 로 옮기면 형식은 맞고 변경으로 센다
            moved = self._record(data, preserved=ids[1:],
                                 items=[{'id': ids[0], 'verdict': '의미 변경', 'evidence': '10억 → 20억'}])
            st = status(moved)
            self.assertEqual(st['status'], '확인 필요')
            self.assertEqual(st['counts']['changed'], 1)
            # 빠진 ID 는 통과하지 못한다
            self.assertEqual(status(self._record(data, preserved=ids[1:]))['status'], '확인 필요')
            # 보존 목록 안의 중복도 막는다
            self.assertEqual(status(self._record(data, preserved=ids + ids[:1]))['status'], '확인 필요')

    def test_record_merge_two_files(self):
        _, _, data = self.pair('서울 매출은 10억원이다.\n\n부산은 지원하지 않는다.',
                               '서울 매출은 20억원이다.\n\n부산은 지원한다.')
        ids = [r['id'] for r in data['risks']]
        self.assertGreaterEqual(len(ids), 2)
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'jev.json', Path(tmp) / 'llm.json'
            a.write_text(json.dumps(self._record(
                data, method='jev', reviewer='jev-1.13.0', preserved=ids[:-1],
                items=[{'id': ids[-1], 'verdict': '판단 불가', 'evidence': '문맥 부족'}])), encoding='utf-8')
            b.write_text(json.dumps(self._record(
                data, preserved=[ids[-1]], items=[])), encoding='utf-8')
            st = review_status(data, [a, b])
            self.assertEqual(st['status'], '독립 검토 완료')      # 뒤 기록이 판단 불가를 덮는다
            self.assertEqual(st['counts']['by_method']['jev'], len(ids) - 1)
            self.assertEqual(st['counts']['by_method']['llm'], 1)

    def test_record_v1_still_accepted(self):
        _, _, data = self.pair('도입을 검토 중이다.', '도입을 확정했다.')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'r.json'
            rec = {'schema_version': 1, 'orig_sha256': data['orig_sha256'],
                   'polished_sha256': data['polished_sha256'], 'independent': True, 'reviewer': 'old',
                   'items': [{'id': r['id'], 'verdict': '보존 확인', 'evidence': '근거'} for r in data['risks']]}
            p.write_text(json.dumps(rec, ensure_ascii=False), encoding='utf-8')
            st = review_status(data, [p])
            self.assertEqual(st['status'], '독립 검토 완료')
            self.assertEqual(st['counts']['preserved'], len(data['risks']))
            # 경로 하나를 그대로 줘도 받는다(옛 호출 방식)
            self.assertEqual(review_status(data, p)['status'], '독립 검토 완료')

    def test_korean_additions(self):
        rules=load_rules()
        def raw(text): return check(text,rules,'줄글').summary['raw']
        self.assertGreater(raw('솔직히 말씀드릴게요. 핵심은 실행입니다.').get('AT-10',0),0)
        self.assertGreater(raw('마케터의 하루를 떠올려 볼까요?').get('AT-11',0),0)
        rep=check('잠재력을 최대한 끌어내고 매끄러운 경험을 제공합니다.',rules,'줄글')
        self.assertEqual(rep.summary['raw'].get('AT-67'),2)
        self.assertFalse(rep.summary['strict_fail'])
        for clean in ['이 경험을 인터뷰로 기록했다.', '표면은 매끄럽다.', '수집, 분석, 보고 순서로 진행한다.', '> 잠재력을 최대한 끌어내고 매끄러운 경험을 제공합니다.']:
            self.assertEqual(raw(clean).get('AT-67',0),0)

    def test_cli_keeps_auto_status_separate(self):
        od, pd, data = self.pair('다음 달 도입을 검토 중이다.', '다음 달 도입을 확정했다.')
        script = Path(__file__).resolve().parents[1] / 'scripts/check_all.py'
        r = subprocess.run([sys.executable, '-X', 'utf8', str(script), '--guide', '없음', '--orig', od.path, pd.path], capture_output=True, text=True, encoding='utf-8')
        self.assertIn('의미 검토: 확인 필요', r.stdout)
        self.assertIn('자동 판정은 문맥의 의미 보존을 보증하지 않습니다.', r.stdout)
        self.assertNotIn('의미 검토: 독립 검토 완료', r.stdout)

    def test_missing_malformed_duplicate_and_evidence(self):
        _, _, data = self.pair('도입을 검토 중이다.', '도입을 확정했다.')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'r.json'
            for value in [[], {}, {'items': 'bad'}]:
                p.write_text(json.dumps(value), encoding='utf-8')
                self.assertEqual(review_status(data,p)['status'], '확인 필요')
            p.write_text('{broken', encoding='utf-8')
            self.assertEqual(review_status(data,p)['status'], '확인 필요')
            rec={'schema_version':1, **{k:data[k] for k in ('orig_sha256','polished_sha256')}, 'independent':True, 'reviewer':'test',
                 'items':[{'id':r['id'],'verdict':'보존 확인','evidence':''} for r in data['risks']]}
            p.write_text(json.dumps(rec), encoding='utf-8')
            self.assertEqual(review_status(data,p)['status'], '확인 필요')
            rec['items'] *= 2
            p.write_text(json.dumps(rec), encoding='utf-8')
            self.assertEqual(review_status(data,p)['status'], '확인 필요')

if __name__ == '__main__':
    unittest.main()
