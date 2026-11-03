"""Render code-audited NIPS workflow; no hardware or model calls.

Run from the repository root: python docs/figures/generate_workflow.py
"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent
INK = '#183047'
MUTED = '#526477'
COLORS = ['#315D94', '#137F83', '#137F83', '#926130', '#735194', '#315D94']


def render(name, size, slide=False):
    fig = plt.figure(figsize=size, facecolor='white')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis('off')
    scale = 1.85 if slide else 1
    title = 15 if slide else 10.5
    ax.text(.035, .959, 'Closed-loop discovery of NIPS membranes',
            fontsize=title, weight='bold', color=INK, va='top')
    ax.text(.035, .919, 'Robotic synthesis  /  compression-derived properties  /  vision-guided experimental decisions',
            fontsize=6.6*scale, color=MUTED, va='top')
    xs = [.035, .365, .695]
    w, h = .27, .281
    yt, yb = .568, .194
    boxes = [
        (xs[0], yt, '01', 'Define the experiment', [
            'Fixed: polymer, base solvent, cosolvent',
            'and NIPS-bath solvent identity / wt%',
            'Seed: filtered history or initial recipe',
            '8 controls: polymer / additive wt%,',
            'mix / bath temperature, casting speed,',
            'air-exposure time, N₂, immersion time',
        ], 'run_loop.py · operator configuration'),
        (xs[1], yt, '02', 'Fabricate autonomously', [
            'Opentrons OT-2 + xArm + bath chiller',
            'Dose stocks → heat / mix → blade cast',
            'Wait in ambient air or dry nitrogen',
            'Immerse in non-solvent bath → retrieve',
            'Record ambient and coupon T / RH',
            'Robot receives recipe via POST /run',
        ], 'protocol-multithreaded.py · robot PC'),
        (xs[2], yt, '03', 'Measure & archive', [
            '4 zero + 4 sample compression curves',
            'Pre-test and post-test photographs',
            'LVDT position check before testing',
            'Batch completion: POST /server/process',
            'Archive 8 CSVs + 2 images + params.json',
            'One condition folder per synthesis run',
        ], 'run_loop.py · data/raw/<condition>/'),
        (xs[2], yb, '04', 'Extract properties & quality', [
            'MECHANICS: chronological zero pairing;',
            'compliance subtraction → stress–strain',
            'GAM + regional fits; thickness / fit checks',
            'E, yield, creep, slopes, fixed-stress strain',
            'Pore Fraction ≔ fitted changepoint strain',
            'VISION: pre-test photo → quality report',
        ], 'curve_segmentation.py · membrane_imaging.py'),
        (xs[1], yb, '05', 'Build experimental memory', [
            'reps.csv: individual measurement results',
            'agg.csv: mean ± SD; pre / post-discard',
            'llm.csv: promoted post-discard outcomes',
            'Attach fit failures + visual quality report',
            'Join current campaign + warm-start data',
            'Retain each run’s material / bath context',
        ], 'llm_context.py · property_context.py'),
        (xs[0], yb, '06', 'Choose & validate next run', [
            'LLM: improve modulus + pore fraction',
            'Balance Pareto gains with exploration',
            'Prompt requests independent validation',
            'Return 8-control JSON → schema check',
            'Apply additive lock + stock feasibility',
            'Undiluted stock: mixing set to 25 °C',
        ], 'activeLearning_29.py · bounds · run_loop.py'),
    ]
    for i, (x, y, num, heading, lines, footer) in enumerate(boxes):
        c = COLORS[i]
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.008,rounding_size=0.009',
                                   facecolor='#F7F9FC', edgecolor='#D8E0E9', linewidth=.8))
        ax.text(x+.009, y+h-.023, num, fontsize=7.3*scale, color=c, weight='bold', va='top')
        ax.text(x+.046, y+h-.023, heading, fontsize=7.3*scale, color=INK, weight='bold', va='top')
        for j, line in enumerate(lines):
            ax.text(x+.009, y+h-.074-j*.026, line, fontsize=6.35*scale, color=INK, va='top')
        ax.text(x+.009, y+.017, footer, fontsize=5.15*scale, color=MUTED, va='bottom')

    def arrow(a, b, color=INK, style='-'):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=8*scale,
                                    lw=1.05, color=color, linestyle=style, zorder=0))
    arrow((.315, yt+h/2), (.353, yt+h/2))
    arrow((.645, yt+h/2), (.683, yt+h/2))
    arrow((.83, yt-.01), (.83, yb+h+.012))
    ax.text(.815, .514, 'Two enabled analysis branches¹', ha='right', fontsize=6.2*scale, color=MUTED)
    arrow((.683, yb+h/2), (.645, yb+h/2))
    arrow((.353, yb+h/2), (.315, yb+h/2))
    arrow((.17, yb+h+.01), (.17, yt-.012), COLORS[0])
    ax.text(.186, .514, 'Next feasible recipe', fontsize=6.2*scale, color=COLORS[0])

    # Separate offline analysis from the physical feedback loop.
    ax.add_patch(FancyBboxPatch((.035, .057), .93, .085,
                 boxstyle='round,pad=0.008,rounding_size=0.007', facecolor='#FBF7EF', edgecolor='#DCCFB9', lw=.8))
    ax.text(.047, .127, 'OFFLINE EVALUATION', fontsize=6*scale, color='#805C2B', weight='bold', va='top')
    ax.text(.047, .102, 'Fit / quality review → HTML logs     |     Repeatability → matched synthesis groups → between-run SD / CV',
            fontsize=6.1*scale, color=INK, va='top')
    ax.text(.047, .077, 'Exact: polymer wt%, N₂, bath-solvent wt%. Tolerances: wait 10 s; bath 3 °C; cast 3 mm/s; RH 5 pp.',
            fontsize=5.7*scale, color=MUTED, va='top')
    arrow((.50, yb-.009), (.50, .151), '#926130', '--')
    ax.text(.035, .027, '¹ Branches dispatch sequentially. Checkpoints support recovery; ambiguous robot submission requires operator review.',
            fontsize=5.5*scale, color=MUTED, va='center')
    for ext in ('svg', 'pdf', 'png'):
        fig.savefig(OUT / (name+'.'+ext), dpi=400 if not slide else 240, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'pdf.fonttype': 42})
    render('nips_workflow_paper', (180/25.4, 140/25.4))
    render('nips_workflow_slide', (16, 9), slide=True)
    print('Wrote paper and slide figures in SVG, PDF and PNG to '+str(OUT))
