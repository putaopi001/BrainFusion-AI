"""Evidence-bound single-panel system schematics; no statistical or clinical claims."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
                     'font.size': 7, 'pdf.fonttype': 42, 'svg.fonttype': 'none',
                     'axes.spines.right': False, 'axes.spines.top': False})
BLUE = '#e6eff7'
GREY = '#f0f2f4'
ORANGE = '#fff0d9'
INK = '#233346'


def canvas(title):
    # 183 x 120 mm in inches, explicit literals also auditable by source QA.
    fig, ax = plt.subplots(figsize=(7.2047244094, 4.7244094488))
    fig.subplots_adjust(left=.03, right=.97, top=.97, bottom=.035)
    ax.set(xlim=(0, 100), ylim=(0, 100)); ax.axis('off')
    ax.text(50, 97, title, ha='center', va='center', fontsize=10, fontweight='bold', color=INK)
    return fig, ax


def box(ax, x, y, width, height, title, body, color=GREY):
    ax.add_patch(Rectangle((x, y), width, height, facecolor=color, edgecolor='#7a8c9d', linewidth=.6))
    ax.text(x + width / 2, y + height - 3.5, title, ha='center', va='top', fontsize=7.5, fontweight='bold', color=INK)
    ax.text(x + width / 2, y + height / 2 - 2, body, ha='center', va='center', fontsize=6.5, linespacing=1.4, color=INK)


def arrow(ax, start, end, dashed=False):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=7,
                               linewidth=.8, color='#536d84', linestyle='--' if dashed else '-'))


def architecture():
    fig, ax = canvas('BrainFusion AI: implemented local system')
    box(ax, 2, 72, 27, 17, 'Patient / case + MRI', 'Four NIfTI sequences\nT1c / T1n / T2w / FLAIR\nSame-grid input required')
    box(ax, 37, 72, 27, 17, 'Vue client + FastAPI', 'Case, task and version APIs\nReadable failure / retry states\nNo synthetic success', BLUE)
    box(ax, 72, 72, 26, 17, 'Persistence on E drive', 'SQLite + MRI / mask files\nVersioned job metadata\nVerified snapshot / restore')
    arrow(ax, (29, 80), (37, 80)); arrow(ax, (64, 80), (72, 80))
    box(ax, 2, 39, 27, 23, 'Serial segmentation job', 'Main Python / PyTorch\nFixed MONAI BraTS SegResNet\nSubprocess inference\nOriginal-space mask + WT/TC/ET', BLUE)
    box(ax, 37, 39, 27, 23, 'Reading + doctor review', 'Four-sequence / three-view MRI\nPhysical measurements\nConfirmation bound to analysis\nIndependent doctor opinion', BLUE)
    box(ax, 72, 39, 26, 23, 'Serial feature job', 'Isolated CPU Python 3.11.17\nPyRadiomics v3.1.0\n20 selected features + clinical input\nResearch prediction / fusion', ORANGE)
    arrow(ax, (15.5, 72), (15.5, 62)); arrow(ax, (50.5, 72), (50.5, 62)); arrow(ax, (85, 72), (85, 62))
    arrow(ax, (29, 51), (37, 51))
    # Routing below boxes keeps paths out of explanatory text.
    arrow(ax, (15.5, 39), (15.5, 31)); arrow(ax, (15.5, 31), (85, 31)); arrow(ax, (85, 31), (85, 39))
    ax.text(30, 33.3, 'Current mask + input lineage', ha='center', fontsize=6.5, color=INK)
    box(ax, 37, 8, 27, 16, 'Report / client-side PDF', 'Current analysis + doctor opinion\nVersion check before download\nNo automatic IDH probability', BLUE)
    arrow(ax, (50.5, 39), (50.5, 24))
    ax.text(2, 16, 'Local prototype only\nDocker not validated\nNo automatic registration', fontsize=6.5, va='center', color=INK)
    ax.text(72, 16, 'Research-only branch\nReference-mask-trained model\nNo diagnostic report write', fontsize=6.5, va='center', color=INK)
    ax.text(50, 2, 'Schematic of implementation, not clinical effectiveness or a new experiment', ha='center', fontsize=6, color=INK)
    return fig


def lineage():
    fig, ax = canvas('BrainFusion AI: version and artifact lineage')
    box(ax, 2, 73, 27, 18, 'Current case / MRI', 'Case ID + current analysis ID\nFour input SHA256 values\nCurrent mask SHA256', BLUE)
    box(ax, 37, 73, 27, 18, 'Case clinical input', 'Associated patient default\nExplicit case override version\nAge + known model sex input')
    box(ax, 72, 73, 26, 18, 'Research / extraction', 'Model + contract SHA256\nWorker provenance SHA256\nFixed selected-feature protocol', ORANGE)
    box(ax, 30, 39, 40, 22, 'Versioned feature task / cache', 'Analysis + input + mask + clinical version\nResearch model + contract + worker source\nSucceeded result only while lineage is current\nOriginal history retained', ORANGE)
    arrow(ax, (15.5, 73), (15.5, 66)); arrow(ax, (15.5, 66), (38, 66)); arrow(ax, (38, 66), (38, 61))
    arrow(ax, (50.5, 73), (50.5, 61))
    arrow(ax, (85, 73), (85, 66)); arrow(ax, (85, 66), (62, 66)); arrow(ax, (62, 66), (62, 61))
    box(ax, 2, 7, 27, 21, 'Analysis-bound report', 'Successful current analysis\nAnalysis-bound review status\nIndependent doctor opinion\nPDF recheck after render', BLUE)
    box(ax, 37, 7, 27, 21, 'Research output', 'Raw target: idh1/2 = 1\nNot risk / detection / treatment\nNo causal explanation\nNot written into report', ORANGE)
    box(ax, 72, 7, 26, 21, 'Changed / missing input', 'Hide stale current result\nKeep historical original\nExplain failure / retry\nNo fabricated probability')
    # The report depends on current analysis, not the feature-task output.
    arrow(ax, (2, 81), (.7, 81)); arrow(ax, (.7, 81), (.7, 17)); arrow(ax, (.7, 17), (2, 17))
    arrow(ax, (50.5, 39), (50.5, 28)); arrow(ax, (70, 48), (85, 48)); arrow(ax, (85, 48), (85, 28))
    ax.text(50, 2, 'Lineage guards detect ordinary file / version changes; not adversarial tamper protection', ha='center', fontsize=6, color=INK)
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qa-scripts', type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    assert evidence['status'] == 'passed' and evidence['database_unchanged_by_capture']
    assert evidence['graph_contract']['research_written_to_diagnostic_report'] is False
    assert evidence['research']['selected_feature_count'] == 20
    sys.path.insert(0, str(args.qa_scripts.resolve()))
    from audit_panel_alignment import require_matplotlib_panel_alignment
    output = args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    manifest = {'scope': 'Single-panel engineering schematics; not statistics, new model results, or journal submission certification.',
                'backend': 'python', 'width_mm': 183, 'height_mm': 120, 'dpi': 600,
                'evidence_sha256': hashlib.sha256(args.evidence.read_bytes()).hexdigest(),
                'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'files': []}
    for name, build in [('system-architecture', architecture), ('version-lineage', lineage)]:
        fig = build(); fig.canvas.draw()
        require_matplotlib_panel_alignment(fig, json_out=str(output / f'{name}.alignment.json'), tolerance_pt=1.5, strict=True)
        fig.savefig(output / f'{name}.pdf', facecolor='white')
        fig.savefig(output / f'{name}.svg', facecolor='white')
        fig.savefig(output / f'{name}.png', dpi=600, facecolor='white')
        for suffix in ['pdf', 'svg', 'png']:
            path = output / f'{name}.{suffix}'
            manifest['files'].append(dict(path=path.name, bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        plt.close(fig)
    (output / 'figure-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(dict(status='rendered_pending_qa', files=len(manifest['files']), source_sha256=manifest['script_sha256'])))


if __name__ == '__main__':
    main()
