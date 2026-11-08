"""Checks for tied statistical inputs and Kazakh-safe metric tokenization."""
import unittest
from analyze_results import holm, friedman, UnicodeTokenizer
from rouge_score.rouge_scorer import RougeScorer


class AnalysisTests(unittest.TestCase):
    def test_holm_known_family(self):
        actual=holm([.01,.04,.03])
        for a,b in zip(actual,[.03,.06,.06]):self.assertAlmostEqual(a,b)

    def test_all_tied_friedman(self):
        rows=[dict(Prompt_ID=p,model_group=m,error_rate_100=0) for p in ['P1','P2']
              for m in ['GPT','Gemini','Claude']]
        result=friedman(rows,'error_rate_100')
        self.assertEqual(result['p'],1)
        self.assertEqual(result['kendalls_w'],0)

    def test_missing_pair_is_rejected(self):
        rows=[dict(Prompt_ID='P1',model_group='GPT',error_rate_100=0)]
        with self.assertRaisesRegex(ValueError,'coverage'):
            friedman(rows,'error_rate_100')

    def test_kazakh_unicode_rouge(self):
        scorer=RougeScorer(['rouge1','rouge2','rougeL'],tokenizer=UnicodeTokenizer())
        result=scorer.score('Қазақ тілінің құнарлы қоры','Қазақ тілінің құнарлы қоры')
        self.assertTrue(all(value.fmeasure==1 for value in result.values()))
        self.assertEqual(UnicodeTokenizer().tokenize('ә ғ қ ң ө ұ ү һ і'),
                         ['ә','ғ','қ','ң','ө','ұ','ү','һ','і'])


if __name__=='__main__':unittest.main()
