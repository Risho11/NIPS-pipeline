"""Export exactly the saved selection in primospire_nmp_campaign_trends.ipynb."""
import json
from pathlib import Path
from notebook_selection import load_notebook_selection
from export_warm_start import export_saved_notebook

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'data' / 'warm_start' / 'primospire_nmp.csv'


def select_primospire_campaign(root=ROOT):
    """Use current notebook settings, including all selected campaigns and filters."""
    data, _ = load_notebook_selection('primospire_nmp_campaign_trends.ipynb', root=root)
    return data


def main():
    print(json.dumps(export_saved_notebook('primospire_nmp_campaign_trends.ipynb'), indent=2))


if __name__ == '__main__':
    main()
