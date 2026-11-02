"""Read the supplied final configuration in the runner's internal format."""
import json


def load_settings(path):
    config = json.loads(path.read_text(encoding='utf-8'))
    if 'tested_models' not in config:
        return config
    models = []
    identities = [('openai', 'gpt6_astra', 'GPT-6 Astra'),
                  ('gemini', 'gemini36_flash', 'Gemini 3.6 Flash'),
                  ('claude', 'claude_sonnet55', 'Claude Sonnet 5.5')]
    for provider, key, name in identities:
        supplied = config['tested_models'][provider]
        if supplied['tools'] != 'disabled':
            raise ValueError('Generation requires disabled tools.')
        model = dict(model_key=key, display_name=name, model_id=supplied['model'],
                     max_output_tokens=supplied['max_output_tokens'])
        if provider == 'openai':
            model['reasoning'] = {'effort': supplied['reasoning_effort']}
        elif provider == 'gemini':
            model['thinking_level'] = supplied['thinking_level']
        else:
            if supplied['adaptive_thinking'] is not True:
                raise ValueError('Claude requires adaptive thinking.')
            model.update(thinking={'type': 'adaptive'}, output_config={'effort': supplied['effort']},
                         max_tokens=supplied['max_output_tokens'])
        models.append(model)
    return dict(config, test_models=models,
                final_runs_per_prompt_model=config['runs_per_prompt_per_model'],
                expected_total_responses=config['planned_tested_model_outputs'])
