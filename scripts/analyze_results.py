"""Reproduce Assignment 4 tables and figures from saved responses and annotations."""
import argparse
from collections import Counter
import csv
import hashlib
import importlib.metadata
import itertools
import json
import os
from pathlib import Path
import platform
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / '.report-deps').exists():
    sys.path.insert(0, str(ROOT / '.report-deps'))
import numpy as np
from scipy import stats
from sacrebleu.metrics import BLEU, CHRF
from rouge_score.rouge_scorer import RougeScorer
from word_count import count_words

OUT = ROOT / 'results/final_analysis'
DATA = ROOT / 'results/selected200_analysis'
JUDGE = ROOT / 'results/selected200_judge_16k'
MODELS = ['GPT', 'Gemini', 'Claude']
CATEGORIES = ['Grammatical', 'Morphological', 'Lexical']
SEED = 20261030
BOOTSTRAPS = 10000


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def write_csv(name, rows):
    if not rows:
        raise ValueError(f'Empty table {name}')
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def holm(pvalues):
    order = np.argsort(pvalues)
    adjusted = np.zeros(len(order))
    running = 0.0
    for position, index in enumerate(order):
        running = max(running, (len(order) - position) * pvalues[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def interval(values):
    return np.quantile(values, [.025, .975]).tolist()


def load_dataset():
    raw = read_csv(DATA / 'combined_600.csv')
    judged = {r['blind_id']: r for r in read_jsonl(JUDGE / 'judge_results.jsonl')}
    candidates = read_jsonl(JUDGE / 'candidate_errors_for_review.jsonl')
    assert len(raw) == len(judged) == 600
    assert len({(r['Prompt_ID'], r['model_group']) for r in raw}) == 600
    primary = []
    for candidate in candidates:
        if candidate['primary_category']:
            verification = candidate.get('human_verification', {})
            if verification.get('decision') != 'CONFIRMED':
                raise ValueError(f'Unconfirmed primary candidate {candidate["candidate_id"]}')
            primary.append(candidate)
    for row in raw:
        text = row['raw_response']
        assert sha_text(text) == row['response_sha256']
        assert count_words(text) == int(row['Word_Count']) > 0
        row['Word_Count'] = int(row['Word_Count'])
        evaluation = judged[row['blind_id']]
        row['evaluation_method'] = evaluation['collection_method']
        row['confirmation_basis'] = 'USER_REPORT'
        for category in CATEGORIES:
            count = sum(c['blind_id'] == row['blind_id'] and c['primary_category'] == category for c in primary)
            row[category.lower() + '_errors'] = count
            row[category.lower() + '_rate'] = 100 * count / row['Word_Count']
        row['primary_errors'] = sum(row[c.lower() + '_errors'] for c in CATEGORIES)
        row['error_rate_100'] = 100 * row['primary_errors'] / row['Word_Count']
        row['has_primary_error'] = int(row['primary_errors'] > 0)
        for key, value in evaluation['result']['scores'].items():
            row[key + '_score'] = value
        row['instruction_compliance'] = int(evaluation['result']['instruction_compliance']['passed'])
        match = re.search(r'Көлемі:\s*(\d+)[–-](\d+)\s*сөз', row['Prompt_KK'])
        row['length_compliance'] = '' if not match else int(int(match[1]) <= row['Word_Count'] <= int(match[2]))
    return raw, primary, candidates, judged


def sha_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def summaries(rows, subset):
    result = []
    for model in MODELS:
        group = sorted([r for r in rows if r['model_group'] == model], key=lambda r: r['Prompt_ID'])
        n = len(group)
        words = np.array([r['Word_Count'] for r in group])
        errors = np.array([r['primary_errors'] for r in group])
        rates = 100 * errors / words
        idx = np.random.default_rng(SEED).integers(0, n, (BOOTSTRAPS, n))
        ci = interval(100 * errors[idx].sum(axis=1) / words[idx].sum(axis=1))
        median_ci = interval(np.median(rates[idx], axis=1))
        q1, median, q3 = np.quantile(rates, [.25, .5, .75])
        record = dict(subset=subset, model=model, responses=n, total_words=int(words.sum()),
            grammatical_errors=sum(r['grammatical_errors'] for r in group),
            morphological_errors=sum(r['morphological_errors'] for r in group),
            lexical_errors=sum(r['lexical_errors'] for r in group),
            primary_errors=int(errors.sum()), errors_per_100_words=float(100 * errors.sum() / words.sum()),
            rate_ci_low=ci[0], rate_ci_high=ci[1], median_rate=float(median), q1=float(q1), q3=float(q3),
            iqr=float(q3-q1), median_ci_low=median_ci[0], median_ci_high=median_ci[1],
            responses_with_errors=int((errors > 0).sum()), percent_with_errors=float(100 * (errors > 0).mean()),
            overall_score_median=float(np.median([r['overall_quality_score'] for r in group])),
            instruction_compliance_percent=float(100 * np.mean([r['instruction_compliance'] for r in group])),
            length_compliance_percent=None)
        lengths = [r['length_compliance'] for r in group if r['length_compliance'] != '']
        if lengths:
            record['length_compliance_percent'] = float(100 * np.mean(lengths))
        for key in ['grammar', 'morphology', 'lexical_naturalness']:
            record[key + '_score_median'] = float(np.median([r[key + '_score'] for r in group]))
        result.append(record)
    return result


def paired_matrix(rows, field):
    lookup = {(r['Prompt_ID'], r['model_group']): r[field] for r in rows}
    prompts = sorted({r['Prompt_ID'] for r in rows})
    if len(lookup) != len(prompts) * 3:
        raise ValueError('Paired prompt coverage is incomplete')
    return np.array([[lookup[(p, m)] for m in MODELS] for p in prompts], dtype=float)


def friedman(rows, field):
    matrix = paired_matrix(rows, field)
    if np.all(matrix == matrix[:, :1]):
        statistic, pvalue = 0.0, 1.0
    else:
        statistic, pvalue = stats.friedmanchisquare(*matrix.T)
    return dict(metric=field, n_prompts=len(matrix), statistic=float(statistic), p=float(pvalue),
                kendalls_w=float(statistic / (len(matrix) * 2)),
                all_tied_blocks=int(np.all(matrix == matrix[:, :1], axis=1).sum()))


def pairwise(rows, field):
    matrix = paired_matrix(rows, field)
    results = []
    for a, b in itertools.combinations(range(3), 2):
        differences = matrix[:, a] - matrix[:, b]
        nonzero = differences[differences != 0]
        if len(nonzero):
            test = stats.wilcoxon(differences, zero_method='wilcox', correction=False, alternative='two-sided', method='asymptotic')
            ranks = stats.rankdata(np.abs(nonzero))
            positive = ranks[nonzero > 0].sum()
            negative = ranks[nonzero < 0].sum()
            effect = float((positive-negative)/(positive+negative))
            statistic, pvalue = float(test.statistic), float(test.pvalue)
        else:
            statistic, pvalue, effect = 0.0, 1.0, 0.0
        ids = np.random.default_rng(SEED).integers(0, len(matrix), (BOOTSTRAPS, len(matrix)))
        delta_ci = interval(np.mean(differences[ids], axis=1))
        results.append(dict(metric=field, model_a=MODELS[a], model_b=MODELS[b],
            n_prompts=len(matrix), nonzero_pairs=len(nonzero), wilcoxon_w=statistic, p=pvalue,
            rank_biserial_a_minus_b=effect, mean_paired_rate_difference=float(differences.mean()),
            difference_ci_low=delta_ci[0], difference_ci_high=delta_ci[1]))
    for row, pvalue in zip(results, holm([r['p'] for r in results])):
        row['p_holm'] = pvalue
    return results


def correlations(rows):
    scores = np.array([r['overall_quality_score'] for r in rows], dtype=float)
    rates = np.array([r['error_rate_100'] for r in rows])
    rho, pvalue = stats.spearmanr(scores, rates)
    # Resample prompts as clusters, preserving all available model responses per prompt.
    prompts = sorted({r['Prompt_ID'] for r in rows})
    grouped = [[i for i, r in enumerate(rows) if r['Prompt_ID'] == p] for p in prompts]
    rng = np.random.default_rng(SEED)
    bootstrap = []
    for _ in range(2000):
        indices = np.concatenate([grouped[i] for i in rng.integers(0, len(grouped), len(grouped))])
        if len(np.unique(scores[indices])) > 1 and len(np.unique(rates[indices])) > 1:
            bootstrap.append(float(stats.spearmanr(scores[indices], rates[indices]).statistic))
    return dict(n=len(rows), rho=float(rho), p=float(pvalue), ci=interval(bootstrap),
                bootstrap_replicates=len(bootstrap), interpretation='Descriptive association from the same evaluation process; not independent validation.')


def validation(rows, judged):
    human = read_csv(DATA / 'human_validation_150_blind.csv')
    by_id = {r['blind_id']: r for r in rows}
    results = []
    matched = 0
    human_spans = 0
    for r in human:
        if not r['annotator_id']:
            raise ValueError('Human annotation sample contains blank records')
        spans = json.loads(r['error_spans_json'])
        predicted = judged[r['blind_id']]['result']['candidate_errors']
        for span in spans:
            human_spans += 1
            matched += any(p['span'] == span['span'] and p['primary_category'] == span['primary_category'] for p in predicted)
    for category in CATEGORIES:
        key = category.lower()
        actual = np.array([int(r[key + '_present']) for r in human])
        predicted = np.array([int(by_id[r['blind_id']][key + '_errors'] > 0) for r in human])
        observed = float((actual == predicted).mean())
        expected = float(actual.mean()*predicted.mean() + (1-actual.mean())*(1-predicted.mean()))
        kappa = None if expected == 1 else (observed-expected)/(1-expected)
        results.append(dict(category=category, n=len(human), human_positive=int(actual.sum()),
            evaluation_positive=int(predicted.sum()), raw_agreement=observed, cohens_kappa=kappa,
            evidence_basis='USER_REPORTED_AGREEMENT', independent_originals_available=False))
    return dict(categories=results, human_primary_spans=human_spans, matched_spans=matched,
        span_recall=None if not human_spans else matched/human_spans,
        note='Labels were transcribed from a global user report of agreement. These values describe asserted concordance and do not independently estimate evaluator reliability or false negatives.')


class UnicodeTokenizer:
    def tokenize(self, text):
        return re.findall(r'[^\W_]+', text.lower(), flags=re.UNICODE)


def translation_metrics(rows, use_bert):
    translations = [r for r in rows if r['Subset'] == 'Reference-based']
    bleu = BLEU(tokenize='13a', lowercase=False, effective_order=False)
    chrf = CHRF(char_order=6, word_order=0, beta=2, whitespace=False)
    rouge = RougeScorer(['rouge1', 'rouge2', 'rougeL'], tokenizer=UnicodeTokenizer(), use_stemmer=False)
    detail = []
    for r in translations:
        score = rouge.score(r['Reference_KK'], r['raw_response'])
        detail.append(dict(blind_id=r['blind_id'], response_id=r['response_id'], model=r['model_group'],
            Prompt_ID=r['Prompt_ID'], rouge1=score['rouge1'].fmeasure,
            rouge2=score['rouge2'].fmeasure, rougeL=score['rougeL'].fmeasure))
    bert_path = OUT / 'bertscore_120.json'
    bert_meta = dict(status='NOT_COMPUTED', reason='Multilingual model weights are required.')
    signature = sha(DATA / 'translation_120.csv')
    if use_bert:
        import torch
        from bert_score import BERTScorer
        torch.set_num_threads(2)
        scorer = BERTScorer(model_type='bert-base-multilingual-cased', num_layers=9,
            device='cpu', idf=False, rescale_with_baseline=False, batch_size=8)
        hypotheses = [r['raw_response'] for r in translations]
        references = [r['Reference_KK'] for r in translations]
        precision, recall, f1 = scorer.score(hypotheses, references, batch_size=8)
        bert_rows = [dict(blind_id=r['blind_id'], precision=float(p), recall=float(q), f1=float(f))
                     for r,p,q,f in zip(translations,precision,recall,f1)]
        max_length = scorer._tokenizer.model_max_length
        truncated = sum(len(scorer._tokenizer.encode(t, truncation=False)) > max_length for t in hypotheses)
        bert_meta = dict(status='COMPUTED', model='bert-base-multilingual-cased', layers=9,
            idf=False, rescale_with_baseline=False, hash=scorer.hash, input_sha256=signature,
            model_revision=getattr(scorer._model.config, '_commit_hash', None),
            hypotheses_over_model_max_length=truncated, rows=bert_rows)
        dump('bertscore_120.json', bert_meta)
    elif bert_path.exists():
        bert_meta = json.loads(bert_path.read_text(encoding='utf-8'))
        if bert_meta.get('input_sha256') != signature:
            raise ValueError('Saved BERTScore inputs changed')
    by_id = {r['blind_id']:r for r in bert_meta.get('rows', [])}
    for r in detail:
        r['bertscore_f1'] = by_id.get(r['blind_id'], {}).get('f1', '')
    aggregate = []
    for model in MODELS:
        group = [r for r in translations if r['model_group'] == model]
        hypotheses = [r['raw_response'] for r in group]
        references = [r['Reference_KK'] for r in group]
        bc = bleu.corpus_score(hypotheses, [references])
        cc = chrf.corpus_score(hypotheses, [references])
        items = [r for r in detail if r['model'] == model]
        aggregate.append(dict(model=model, n=40, BLEU=bc.score, ChrF=cc.score,
            ROUGE1_F1=float(np.mean([r['rouge1'] for r in items])),
            ROUGE2_F1=float(np.mean([r['rouge2'] for r in items])),
            ROUGEL_F1=float(np.mean([r['rougeL'] for r in items])),
            BERTScore_F1=None if not by_id else float(np.mean([r['bertscore_f1'] for r in items]))))
    return aggregate, detail, dict(bleu_signature=str(bleu.get_signature()),
        chrf_signature=str(chrf.get_signature()), rouge_tokenizer='Unicode letter and digit sequences, lowercase, no stemming',
        text_policy='Unmodified full raw response, including extra commentary', bert={k:v for k,v in bert_meta.items() if k!='rows'})


def figures(summary, subgroup):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    colors = ['#285780','#43806B','#A45B38']
    oe = [r for r in summary if r['subset']=='Open-ended']
    fig, ax = plt.subplots(figsize=(7.3,3.7))
    x = np.arange(3)
    vals = np.array([r['errors_per_100_words'] for r in oe])
    err = np.array([[r['rate_ci_low'] for r in oe], [r['rate_ci_high'] for r in oe]])
    ax.bar(x, vals, color=colors, width=.55)
    ax.errorbar(x,vals,yerr=np.array([vals-err[0],err[1]-vals]),fmt='none',color='black',capsize=5)
    ax.set_xticks(x,MODELS);ax.set_ylabel('Primary errors per 100 words')
    ax.set_ylim(0,max(err[1])*1.22)
    for i,v in enumerate(vals):ax.text(i,err[1,i]+max(err[1])*.04,f'{v:.3f}',ha='center')
    ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    fig.tight_layout();fig.savefig(OUT/'figure_1_primary_rates.png',dpi=220);plt.close(fig)
    fig, ax = plt.subplots(figsize=(7.3,3.8))
    bottom = np.zeros(3)
    for category,color in zip(CATEGORIES,['#285780','#43806B','#A45B38']):
        values=np.array([100*r[category.lower()+'_errors']/r['total_words'] for r in oe])
        ax.bar(x,values,bottom=bottom,label=category,color=color,width=.55);bottom+=values
    ax.set_xticks(x,MODELS);ax.set_ylabel('Primary errors per 100 words')
    ax.legend(frameon=False,ncol=3,loc='upper center',bbox_to_anchor=(.5,1.17))
    ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    fig.tight_layout();fig.savefig(OUT/'figure_2_error_categories.png',dpi=220);plt.close(fig)
    fig, ax=plt.subplots(figsize=(7.3,3.8))
    levels=['Basic','Intermediate','Advanced','Expert']
    for model,color in zip(MODELS,colors):
        values=[next(r['errors_per_100_words'] for r in subgroup if r['dimension']=='Difficulty' and r['group']==level and r['model']==model) for level in levels]
        ax.plot(levels,values,marker='o',color=color,label=model)
    ax.set_ylabel('Primary errors per 100 words');ax.legend(frameon=False)
    ax.grid(axis='y',alpha=.18);fig.tight_layout();fig.savefig(OUT/'figure_3_difficulty.png',dpi=220);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bert',action='store_true',help='Compute multilingual BERTScore on CPU; downloads public model weights.')
    args=parser.parse_args()
    started=time.perf_counter();OUT.mkdir(exist_ok=True)
    rows, primary, candidates, judged=load_dataset()
    write_csv('final_dataset_600.csv', rows)
    oe=[r for r in rows if r['Subset']=='Open-ended']
    translation=[r for r in rows if r['Subset']=='Reference-based']
    summary=summaries(rows,'All')+summaries(oe,'Open-ended')+summaries(translation,'Reference-based')
    write_csv('model_summary.csv',summary)
    tests=[dict(subset='Open-ended',**friedman(oe,'error_rate_100')),
           dict(subset='Reference-based',**friedman(translation,'error_rate_100'))]
    pairs=[]
    for subset, group, test in [('Open-ended',oe,tests[0]),('Reference-based',translation,tests[1])]:
        if test['p']<.05:
            pairs.extend(dict(subset=subset,**r) for r in pairwise(group,'error_rate_100'))
    category_tests=[friedman(oe,c.lower()+'_rate') for c in CATEGORIES]
    for test,adjusted in zip(category_tests,holm([t['p'] for t in category_tests])):
        test['p_holm']=adjusted
        if adjusted<.05:
            pairs.extend(dict(subset='Open-ended category',**r) for r in pairwise(oe,test['metric']))
    write_csv('pairwise_comparisons.csv',pairs)
    subgroup=[]
    for dimension in ['Difficulty','Task_Category']:
        for value in sorted({r[dimension] for r in oe}):
            group=[r for r in oe if r[dimension]==value]
            subgroup.extend(dict(dimension=dimension,group=value,**s) for s in summaries(group,'Open-ended'))
    write_csv('subgroup_summary.csv',subgroup)
    human=validation(rows,judged)
    sample_ids={r['blind_id'] for r in read_csv(DATA/'human_validation_150_blind.csv')}
    correlations_result=dict(all=correlations(rows),open_ended=correlations(oe),
        sample_150=correlations([r for r in rows if r['blind_id'] in sample_ids]))
    lookup={r['blind_id']:r for r in rows}
    cases=[];used=set()
    for category in CATEGORIES:
        eligible=sorted([c for c in primary if c['primary_category']==category],key=lambda c:c['candidate_id'])
        selected=0
        for c in eligible:
            if c['blind_id'] in used:continue
            row=lookup[c['blind_id']];used.add(c['blind_id']);selected+=1
            cases.append(dict(case=len(cases)+1,candidate_id=c['candidate_id'],blind_id=c['blind_id'],
                Prompt_ID=row['Prompt_ID'],model=row['model_group'],category=category,
                span=c['span'],correction=c.get('suggested_correction') or 'Requires contextual adjudication',
                rationale=c['justification'],supplementary_labels=' | '.join(c['supplementary_labels']),
                confirmation_basis='USER_REPORT'))
            if selected==10:break
    assert len(cases)==30 and len(used)==30
    write_csv('error_analysis_30.csv',cases)
    metrics,detail,metric_config=translation_metrics(rows,args.bert)
    write_csv('translation_metrics.csv',metrics);write_csv('translation_per_response.csv',detail)
    supplementary=Counter(label for c in candidates for label in c['supplementary_labels'])
    method_counts=Counter(r['evaluation_method'] for r in rows)
    # Restrict to the common Codex evaluator as an explicitly post hoc sensitivity check.
    common=[p for p in {r['Prompt_ID'] for r in oe} if all(lookup_row['evaluation_method']=='ASSISTANT_REVIEW' for lookup_row in oe if lookup_row['Prompt_ID']==p)]
    common_rows=[r for r in oe if r['Prompt_ID'] in common]
    results=dict(seed=SEED,bootstrap_replicates=BOOTSTRAPS,summary=summary,global_tests=tests,
        category_tests=category_tests,pairwise=pairs,human_validation=human,correlations=correlations_result,
        translation=metrics,translation_configuration=metric_config,
        supplementary=dict(supplementary),evaluation_methods=dict(method_counts),
        same_evaluator_sensitivity=friedman(common_rows,'error_rate_100'),
        unique_error_responses=sum(r['has_primary_error'] for r in rows),
        human_sample_by_difficulty=dict(Counter(lookup[b]['Difficulty'] for b in sample_ids)),
        source_dates_missing=sum(not r['source_date_value'] for r in rows),
        runtime_seconds=time.perf_counter()-started)
    figures(summary,subgroup)
    results['runtime_seconds'] = time.perf_counter()-started
    dump('statistics.json',results)
    paths=[DATA/'combined_600.csv', DATA/'human_validation_150_blind.csv',
           DATA/'translation_120.csv',JUDGE/'judge_results.jsonl',JUDGE/'candidate_errors_for_review.jsonl',Path(__file__)]
    packages=['numpy','scipy','matplotlib','sacrebleu','rouge-score','python-docx',
              'bert-score','torch','transformers']
    dump('analysis_manifest.json',dict(python=sys.version,platform=platform.platform(),seed=SEED,
        bootstrap_replicates=BOOTSTRAPS,input_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},
        software={p:importlib.metadata.version(p) for p in packages},
        elapsed_seconds=time.perf_counter()-started,
        human_evidence='User-reported matching annotations; original independent labels unavailable.',
        wilcoxon='two-sided asymptotic, zero_method wilcox, no continuity correction, average ranks for ties',
        bootstrap='Percentile prompt bootstrap; paired prompt indices preserved across models. Correlations use 2000 cluster replicates.',
        output_sha256={p.name:sha(p) for p in OUT.iterdir()
                       if p.is_file() and p.name not in ('analysis_manifest.json','report_checks.json')}))
    print(json.dumps(dict(summary=summary[:6],tests=tests,validation=human,translation=metrics),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
