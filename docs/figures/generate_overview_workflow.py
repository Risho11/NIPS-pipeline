"""Minimal seven-stage workflow with explicit, non-crossing edge routing."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

OUT = Path(__file__).resolve().parent
INK = '#242B30'
GREY = '#626B71'
BLUE = '#2D617A'


def render(stem, size, slide=False):
    fig = plt.figure(figsize=size, facecolor='white')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis('off')
    title_fs, detail_fs = (17, 13) if slide else (9, 7.3)
    w, h = .227, .145
    nodes = {
        'fabricate': (.158, .715, 'Membrane fabrication', 'OT-2 + xArm\nCasting, exposure and NIPS'),
        'measure': (.467, .715, 'Experimental measurements', '4 zero + 4 sample curves\nPre- and post-test images'),
        'mechanics': (.780, .820, 'Mechanical analysis', 'Compliance correction\nStress–strain fitting'),
        'vision': (.780, .580, 'Image assessment', 'Pre-test vision model\nCoverage and visible defects'),
        'evidence': (.780, .245, 'Experimental record', 'Properties, variability and quality\nCampaign + historical data'),
        'learn': (.467, .245, 'Next-experiment selection', 'LLM-guided search\nModulus + pore fraction'),
        'recipe': (.158, .245, 'Feasible recipe', 'Parameter and stock checks\nApply campaign constraints'),
    }

    def port(key, side):
        x, y, _, _ = nodes[key]
        return {'left': (x-w/2, y), 'right': (x+w/2, y),
                'top': (x, y+h/2), 'bottom': (x, y-h/2)}[side]

    def path(points, arrow=True, color=INK, lw=.9):
        # Straight orthogonal segments; arrowhead only on the destination segment.
        if len(points) > 2:
            ax.plot([p[0] for p in points[:-1]], [p[1] for p in points[:-1]],
                    color=color, lw=lw, solid_capstyle='butt', zorder=1)
        a,b = points[-2:]
        if arrow:
            ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=11 if slide else 7,
                         shrinkA=0, shrinkB=0, lw=lw, color=color, zorder=1))
        else:
            ax.plot([a[0],b[0]],[a[1],b[1]],color=color,lw=lw,zorder=1)

    path([port('fabricate','right'),port('measure','left')])
    # Split: one measurement set supplies two analytical paths.
    split_x = .622
    path([port('measure','right'),(split_x,.715)],arrow=False)
    for key in ['mechanics','vision']:
        y=nodes[key][1]
        path([(split_x,.715),(split_x,y),port(key,'left')])
    ax.plot(split_x,.715,'o',ms=2.4,color=INK)
    # Merge outside both analysis boxes; no edges pass through a node.
    merge_x, merge_y = .955,.405
    path([port('mechanics','right'),(merge_x,.820),(merge_x,merge_y)],arrow=False)
    path([port('vision','right'),(merge_x,.580)],arrow=False)
    path([(merge_x,merge_y),(.780,merge_y),port('evidence','top')])
    ax.plot(merge_x,.580,'o',ms=2.4,color=INK)
    path([port('evidence','left'),port('learn','right')])
    path([port('learn','left'),port('recipe','right')],color=BLUE,lw=1.1)
    path([port('recipe','top'),port('fabricate','bottom')],color=BLUE,lw=1.1)
    ax.text(.171,.48,'Next run',fontsize=detail_fs,color=BLUE,va='center',ha='left')

    for key,(x,y,title,detail) in nodes.items():
        color=BLUE if key in ['learn','recipe'] else INK
        ax.add_patch(Rectangle((x-w/2,y-h/2),w,h,facecolor='white',edgecolor=color,lw=.85,zorder=3))
        ax.text(x,y+.028,title,ha='center',va='center',fontsize=title_fs,weight='medium',color=color,zorder=4)
        ax.text(x,y-.025,detail,ha='center',va='center',fontsize=detail_fs,color=GREY,linespacing=1.5,zorder=4)

    ax.text(.045,.950,'Automated NIPS membrane workflow',fontsize=title_fs+2,color=INK,va='top',weight='medium')
    ax.text(.045,.068,'The LLM prompt requests independent synthesis repeats for candidate validation.',fontsize=detail_fs,color=GREY)
    ax.text(.045,.033,'Pore fraction is estimated from the fitted compression changepoint.',fontsize=detail_fs,color=GREY)
    for ext in ('pdf','svg','png'):
        fig.savefig(OUT/(stem+'.'+ext),dpi=400 if not slide else 240,facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'svg.fonttype':'none'})
    render('nips_workflow_overview_paper',(180/25.4,110/25.4))
    render('nips_workflow_overview_slide',(16,9),True)
    print('Rendered seven-stage overview in paper and slide formats.')
