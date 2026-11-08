"""Import completed selected-200 XLSX and prepare reproducible blinded evaluation."""
import argparse
import csv
import hashlib
import json
import random
import shutil
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from generate_responses import ROOT, sha
from selected_plan import load_selected_plan
from word_count import count_words

SEED = 20261030
DEFAULT_OUTPUT = ROOT / 'results/selected200_analysis'
SHEETS = {'GPT_Run_A_200': 'GPT', 'Gemini_Run_A_200': 'Gemini', 'Claude_Run_A_200': 'Claude'}
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_workbook(path):
    """Read stored cell values directly, preserving whitespace and line breaks."""
    with zipfile.ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', NS):
                strings.append(''.join(t.text or '' for t in item.findall('.//s:t', NS)))
        relations = {r.get('Id'): r.get('Target') for r in
                      ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        sheets = {}
        for sheet in ET.fromstring(archive.read('xl/workbook.xml')).findall('s:sheets/s:sheet', NS):
            name = sheet.get('name')
            if name not in SHEETS:
                continue
            relation = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            target = relations[relation]
            target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            rows = []
            for row in ET.fromstring(archive.read(target)).findall('s:sheetData/s:row', NS):
                cells = {}
                for cell in row.findall('s:c', NS):
                    if cell.find('s:f', NS) is not None:
                        raise ValueError(f'{name}: formula in source data requires review')
                    value = cell.find('s:v', NS)
                    text = value.text or '' if value is not None else ''.join(
                        t.text or '' for t in cell.findall('.//s:t', NS))
                    if cell.get('t') == 's':
                        text = strings[int(text)]
                    cells[cell.get('r').rstrip('0123456789')] = text
                rows.append(cells)
            header = rows[0]
            sheets[name] = [{label: row.get(col, '') for col, label in header.items()}
                            for row in rows[1:] if any(row.values())]
    if set(sheets) != set(SHEETS):
        raise ValueError('Missing required model response sheets')
    return sheets


def write_csv(path, rows):
    if not rows:
        raise ValueError(f'No rows for {path}')
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def write_jsonl(path, rows):
    temp = path.with_suffix('.tmp')
    temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    temp.replace(path)


def prepare(source, output=DEFAULT_OUTPUT):
    source_hash = sha(source)
    manifest_path = output / 'import_manifest.json'
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding='utf-8'))
        if existing['source_sha256'] != source_hash:
            raise ValueError('Different workbook already imported here. Use a separate output directory.')
        for name, digest in existing['output_sha256'].items():
            if sha(output / name) != digest:
                raise ValueError(f'Existing prepared file changed: {name}. Refusing to overwrite.')
        print('Workbook already imported, prepared-file hashes verified.')
        return
    expected = {run['prompt']['Prompt_ID']: run['prompt'] for run in load_selected_plan()}
    records = []
    summary = {}
    for sheet, rows in read_workbook(source).items():
        group = SHEETS[sheet]
        ids = [r['Prompt_ID'] for r in rows]
        if len(ids) != 200 or len(set(ids)) != 200 or set(ids) != set(expected):
            raise ValueError(f'{sheet}: expected the exact 200 selected prompt IDs once each')
        for row in rows:
            prompt = expected[row['Prompt_ID']]
            for field in ['Prompt_KK', 'Subset', 'Task_Category', 'Difficulty']:
                if row[field] != prompt[field]:
                    raise ValueError(f'{sheet}/{row["Prompt_ID"]}: mismatched {field}')
            response = row['Raw_Response']
            if not response.strip():
                raise ValueError(f'{sheet}/{row["Prompt_ID"]}: empty response')
            records.append(dict(response_id=f'{group}_{row["Prompt_ID"]}_A',
                model_group=group, run_label='A', Prompt_ID=row['Prompt_ID'],
                Subset=prompt['Subset'], Task_Category=prompt['Task_Category'],
                Domain=prompt['Domain'], Difficulty=prompt['Difficulty'],
                Prompt_KK=prompt['Prompt_KK'], raw_response=response, Word_Count=count_words(response),
                response_sha256=hashlib.sha256(response.encode('utf-8')).hexdigest(),
                source_sheet=sheet, source_status=row.get('Status', ''),
                source_date_value=row.get('Date', ''), source_notes=row.get('Notes', ''),
                exact_model_version='', model_identity_status='UNVERIFIED',
                collection_settings_status='UNVERIFIED', Source_EN=prompt['Source_EN'],
                Reference_KK=prompt['Reference_KK']))
        summary[group] = dict(responses=len(rows), empty_responses=0, duplicate_prompt_ids=0,
                              missing_dates=sum(not r.get('Date') for r in rows),
                              unverified_exact_model_versions=len(rows))
    records.sort(key=lambda row: row['response_id'])
    random.Random(SEED).shuffle(records)
    mapping = []
    blind = []
    for index, row in enumerate(records, 1):
        row['blind_id'] = f'B{index:04d}'
        mapping.append({key: row[key] for key in ['blind_id', 'response_id', 'model_group', 'Prompt_ID']})
        blind.append({key: row[key] for key in ['blind_id', 'Prompt_KK', 'raw_response', 'Task_Category', 'Subset']})
    # Equal model quotas, proportional task-group strata using largest remainders.
    rng = random.Random(SEED)
    sample = []
    for group in sorted(SHEETS.values()):
        strata = defaultdict(list)
        for row in records:
            if row['model_group'] == group:
                strata[(row['Subset'], row['Task_Category'])].append(row)
        counts = {key: len(values) * 50 // 200 for key, values in strata.items()}
        priorities = sorted(strata, key=lambda key: (-(len(strata[key]) * 50 % 200), key))
        for key in priorities[:50 - sum(counts.values())]:
            counts[key] += 1
        for key in sorted(strata):
            pool = sorted(strata[key], key=lambda row: row['response_id'])
            sample.extend(rng.sample(pool, counts[key]))
    rng.shuffle(sample)
    human = []
    for row in sample:
        item = {key: row[key] for key in ['blind_id', 'Prompt_KK', 'raw_response', 'Word_Count']}
        item.update(annotator_id='', grammatical_present='', morphological_present='', lexical_present='',
                    grammatical_count='', morphological_count='', lexical_count='',
                    error_spans_json='', notes='')
        human.append(item)
    translations = [r for r in records if r['Subset'] == 'Reference-based']
    if len(records) != 600 or len(sample) != 150 or len(translations) != 120:
        raise ValueError('Unexpected combined/sample/translation counts')
    output.mkdir(parents=True, exist_ok=True)
    snapshot = output / 'source_tracker.xlsx'
    if snapshot.exists() and sha(snapshot) != source_hash:
        raise ValueError('Source snapshot conflict')
    shutil.copyfile(source, snapshot)
    write_csv(output / 'combined_600.csv', records)
    write_csv(output / 'judge_mapping_PRIVATE.csv', mapping)
    write_jsonl(output / 'judge_input_blind.jsonl', blind)
    write_csv(output / 'human_validation_150_blind.csv', human)
    write_csv(output / 'human_150_mapping_PRIVATE.csv', [
        {key: r[key] for key in ['blind_id', 'response_id', 'model_group', 'Prompt_ID']} for r in sample])
    write_csv(output / 'translation_120.csv', translations)
    qc = dict(models=summary, total_responses=600, human_sample=150, translations=120,
              human_sample_by_model=dict(Counter(r['model_group'] for r in sample)),
              shared_prompt_ids=200, seed=SEED, model_identity_verified=False,
              date_values='Stored source values, including Excel serials. Missing dates left empty.')
    (output / 'qc_summary.json').write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding='utf-8')
    generated = ['source_tracker.xlsx', 'combined_600.csv', 'judge_mapping_PRIVATE.csv',
                 'judge_input_blind.jsonl', 'human_validation_150_blind.csv',
                 'human_150_mapping_PRIVATE.csv', 'translation_120.csv', 'qc_summary.json']
    manifest = dict(source_filename=source.name, source_sha256=source_hash, seed=SEED,
        output_sha256={name: sha(output / name) for name in generated},
        preparation_script_sha256=sha(Path(__file__)), word_count_script_sha256=sha(ROOT / 'scripts/word_count.py'))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Imported 600 responses, prepared 600 blind inputs, 150 human-validation records, 120 translations: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        prepare(args.workbook, args.output_dir)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'ERROR: {error}\n')
