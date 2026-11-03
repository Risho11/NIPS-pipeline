"""Detailed hardware/software graph. Run with Python + Matplotlib."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon

OUT = Path(__file__).resolve().parent
COLORS = ['#365F94', '#00847E', '#00847E', '#B37326', '#7955A0', '#365F94']
LANES = ['CAMPAIGN / HTTP', 'ROBOT PREPARATION', 'FORMATION / TESTING', 'MECHANICAL ANALYSIS', 'VISION / MEMORY', 'DECISION / RECOVERY']
NODES = {}


def node(key, col, row, label, kind='process'):
    NODES[key] = (col, row, label, kind)


# Each brick corresponds to a specific operation, artifact or decision.
for args in [
 ('config',0,0,'Operator: materials\n+ bath composition','data'),
 ('history',0,1,'Filtered warm-start\nCSV history','data'),
 ('seed',0,2,'Warm-start suggestion\nor INITIAL_PARAMS'),
 ('schema',0,3,'Check JSON keys / types\n+ fixed material context'),
 ('stock',0,4,'Additive lock → stock\nfeasibility projection'),
 ('health',0,5,'Robot health / journal\n+ request UUID'),
 ('send',0,6,'POST /run\nurl_29.run_test()'),
 ('callback',0,8,'POST /server/process\nparams + protocol log'),
 ('archive',0,9,'Copy latest 8 CSVs\n+ 2 photographs'),
 ('raw',0,10,'data/raw/<condition>/\nparams.json + files','data'),
 ('checkpoint',0,11,'.pipeline_state.json\ncompleted-stage journal','data'),
 ('robot',1,0,'Robot accepts recipe\nprotocol-multithreaded'),
 ('chill',1,1,'Bath chiller\ngo_to_temperature()'),
 ('zero',1,2,'xArm: clean coupon\n→ 4 zero tests'),
 ('dope',1,3,'OT-2: prepare 1000 µL\nstock dosing + heat / mix'),
 ('join',1,4,'JOIN: bath ready\n+ zeroed coupon ready','gate'),
 ('dispense',1,5,'OT-2 dispenses\nonto casting coupon'),
 ('cast',1,6,'xArm blade pullcast\nselected speed (mm/s)'),
 ('clean',1,7,'Background knife clean\ndelayed; arm-lock gated'),
 ('uno',1,9,'Arduino Uno\ntrigger compression'),
 ('safe',1,10,'LVDT safe AND\nCSV age < 30 s?','gate'),
 ('stop',1,11,'Unsafe / stale data\nSTOP robot protocol','stop'),
 ('n2',2,0,'Nitrogen enabled?','gate'),
 ('blow',2,1,'YES: Uno N₂ valve\n+ xArm hovering cap'),
 ('ambient',2,2,'NO: ambient wait\n(no nitrogen flow)'),
 ('sensors',2,3,'Read coupon + ambient\ntemperature / humidity'),
 ('bath',2,4,'xArm: immerse coupon\nstart NIPS timer + ring'),
 ('rinse',2,5,'xArm: second bath\nfixed 45 min wait'),
 ('pre',2,6,'Camera box: pre-test\nGET /camera/snapshot'),
 ('sample',2,7,'xArm → tester\n4 sample measurements'),
 ('post',2,8,'Camera box: post-test\nGET /camera/snapshot'),
 ('discard',2,9,'xArm discards coupon\nrelease hardware locks'),
 ('csv',2,10,'Newton CSV export\nload + LVDT + set point','data'),
 ('photo',2,11,'OpenCV camera index 2\nJPEG snapshots','data'),
 ('dispatch',3,0,'master_processing\nenabled branch dispatch'),
 ('pair',3,1,'Pair zero / sample\nchronologically'),
 ('trim',3,2,'Trim loading / creep\n1 N cleanup; in → µm'),
 ('subtract',3,3,'Interpolate zero by load\nsubtract frame compliance'),
 ('thick',3,4,'Thickness: 10–40 N fit\nextrapolate to zero load'),
 ('valid',3,5,'Thickness > 50 µm?','gate'),
 ('strain',3,6,'Corrected displacement\n→ strain; load → stress'),
 ('gam',3,7,'GAM smoothing\n+ elastic boundary'),
 ('fits',3,8,'Elastic + plateau +\ndensification fits'),
 ('props',3,9,'E / yield / creep / slopes\npore fraction = changepoint'),
 ('fit',3,10,'goodFit_eval()\nscore + failure reasons'),
 ('reps',3,11,'reps.csv + fit plots\nindividual measurements','data'),
 ('vision',4,0,'image_processing\nselect earliest JPEG'),
 ('rawimage',4,1,'SEND_RAW_IMAGE?','gate'),
 ('vllm',4,2,'YES: vision LLM\nmembrane_quality_llm'),
 ('legacy',4,3,'NO: legacy pixel math\n+ probe-point selection'),
 ('quality',4,4,'Presence / coverage /\nuniformity / defects'),
 ('failed',4,5,'No-membrane outcome\nretain failure evidence'),
 ('agg',4,7,'agg.csv: mean ± SD\npre / post-discard','data'),
 ('promote',4,8,'Promote post-discard\n→ llm.csv'),
 ('attach',4,9,'Attach quality report\n+ fit failure notes'),
 ('memory',4,10,'Join live + warm history\nkeep original bath context'),
 ('review',4,11,'OFFLINE: HTML fit / quality\nreview + repeatability'),
 ('context',5,0,'Structured observations\n+ diversity coverage'),
 ('al',5,1,'LLM: modulus + pore fraction\nbalanced exploration'),
 ('repeat',5,2,'Prompt: independently\nrepeat promising candidates'),
 ('json',5,3,'8-control JSON\nparse + schema check'),
 ('locks',5,4,'Locks + feasible stocks\nundiluted stock → 25 °C'),
 ('save',5,5,'Save next-params JSON\nrecommendation checkpoint','data'),
 ('submit',5,6,'Health / journal check\ncheckpoint → submit'),
 ('error',5,8,'Enabled branch / LLM\nfailure → stop round','stop'),
 ('restart',5,9,'Restart: inspect latest\nincomplete condition'),
 ('resume',5,10,'Reuse completed stages\nretry missing stages'),
 ('ambiguous',5,11,'Unresolved submission?\noperator verification','gate'),
]:
    node(*args)

EDGES = []
def link(a,b,label='',style='normal'):
    EDGES.append((a,b,label,style))
def chain(keys, style='normal'):
    for a,b in zip(keys,keys[1:]): link(a,b,style=style)

chain(['config','history','seed','schema','stock','health','send'])
link('send','robot','HTTP', 'cross')
for b in ['chill','zero','dope']: link('robot',b,style='fork')
for a in ['chill','zero','dope']: link(a,'join',style='fork')
chain(['join','dispense','cast'])
link('cast','clean','background','optional')
link('cast','n2',style='cross')
link('n2','blow','yes')
link('n2','ambient','no','fork')
link('blow','sensors',style='fork')
link('ambient','sensors')
chain(['sensors','bath','rinse','pre','sample','post','discard'])
link('discard','callback',style='cross')
chain(['callback','archive','raw','checkpoint'])
link('zero','uno',style='fork')
link('sample','uno',style='cross')
link('uno','safe')
link('safe','stop','no','error')
link('safe','sample','yes / next position','cross')
link('uno','csv',style='data')
link('pre','photo',style='data')
link('post','photo',style='data')
link('csv','archive',style='data')
link('photo','archive',style='data')
link('raw','dispatch','saved batch','data')
chain(['dispatch','pair','trim','subtract','thick','valid'])
link('valid','strain','yes')
link('valid','failed','no','cross')
chain(['strain','gam','fits','props','fit','reps'])
link('dispatch','vision','quality branch','cross')
chain(['vision','rawimage','vllm'])
link('rawimage','legacy','no','optional')
link('vllm','quality')
link('legacy','quality',style='optional')
link('reps','agg',style='cross')
chain(['agg','promote','attach','memory'])
link('quality','attach',style='data')
link('failed','agg',style='data')
link('memory','context',style='cross')
link('history','memory',style='data')
chain(['context','al','repeat','json','locks','save','submit'])
link('submit','send','NEXT EXPERIMENT','feedback')
link('checkpoint','restart',style='data')
chain(['restart','resume','ambiguous'])
link('resume','dispatch','missing stages','recovery')
link('ambiguous','submit','only if resolved','recovery')
link('fit','error','raises','error')
link('vllm','error','raises','error')
link('al','error','fails','error')
link('agg','review',style='data')
link('reps','review',style='data')


def render(name, figsize, slide=False):
    fig = plt.figure(figsize=figsize, facecolor='white')
    ax = fig.add_axes([0,0,1,1]); ax.set(xlim=(0,1),ylim=(0,1)); ax.axis('off')
    fs = 8.2 if not slide else 10.4
    xs = [.091+.164*i for i in range(6)]
    ys = [.842-.061*i for i in range(12)]
    w,h=.135,.039
    ax.text(.021,.978,'NIPS membrane discovery | hardware, software and feedback flow',
            fontsize=15 if slide else 13,weight='bold',color='#183047',va='top')
    ax.text(.021,.941,'Small bricks = individual operations   •   Diamonds = decisions / synchronization   •   Tinted bricks = stored data',
            fontsize=fs-1,color='#526477',va='top')
    for i,title in enumerate(LANES):
        ax.add_patch(FancyBboxPatch((xs[i]-.078,.129),.156,.781,boxstyle='round,pad=0.001',
                     facecolor=COLORS[i],alpha=.045,edgecolor='none',zorder=0))
        ax.text(xs[i],.895,title,ha='center',va='center',weight='bold',fontsize=fs-1.4,color=COLORS[i])

    def pos(key):
        c,r,_,_=NODES[key]; return xs[c],ys[r]
    # Edges first; use lane gutters for non-local connections.
    for idx,(a,b,label,style) in enumerate(EDGES):
        x1,y1=pos(a); x2,y2=pos(b)
        color={'data':'#8795A6','optional':'#9AA1A9','error':'#B64E4E',
               'recovery':'#9D6D32','feedback':'#2456A0'}.get(style,'#587080')
        dash='--' if style in ('data','optional','recovery','error') else '-'
        lw=1.35 if style=='feedback' else .65
        if style=='feedback':
            gutter=.116
            g1=x1+w/2+.007
            g2=x2-w/2-.007
            pts=[(x1+w/2,y1),(g1,y1),(g1,gutter),(g2,gutter),(g2,y2),(x2-w/2,y2)]
        elif abs(x1-x2)<.001 and abs(y1-y2)<.067:
            sign=1 if y2>y1 else -1
            pts=[(x1,y1+sign*h/2),(x2,y2-sign*h/2)]
        elif abs(y1-y2)<.001:
            sign=1 if x2>x1 else -1
            pts=[(x1+sign*w/2,y1),(x2-sign*w/2,y2)]
        elif abs(x1-x2)<.001:
            gutter=x1-w/2-.005-(idx%3)*.002
            pts=[(x1-w/2,y1),(gutter,y1),(gutter,y2),(x2-w/2,y2)]
        else:
            sign=1 if x2>x1 else -1
            if abs(x2-x1)>.18:
                # Long data connections use inter-row tracks, avoiding node interiors.
                track=y1-.026-(idx%3)*.002
                g2=x2-sign*(w/2+.007)
                pts=[(x1,y1-h/2),(x1,track),(g2,track),(g2,y2),(x2-sign*w/2,y2)]
            else:
                mid=(x1+x2)/2+(idx%3-1)*.003
                pts=[(x1+sign*w/2,y1),(mid,y1),(mid,y2),(x2-sign*w/2,y2)]
        ax.plot([p[0] for p in pts],[p[1] for p in pts],color=color,lw=lw,ls=dash,zorder=1)
        ax.add_patch(FancyArrowPatch(pts[-2],pts[-1],arrowstyle='-|>',mutation_scale=5.5,
                                    lw=lw,color=color,linestyle=dash,zorder=1))
        if label and style not in ('data','cross','error','recovery','feedback'):
            ax.text((pts[0][0]+pts[1][0])/2+.003,(pts[0][1]+pts[1][1])/2,
                    label,fontsize=fs-3.2,color=color,ha='left',va='center',zorder=5,
                    bbox=dict(facecolor='white',edgecolor='none',pad=.15))
    for key,(c,r,label,kind) in NODES.items():
        x,y=pos(key); color=COLORS[c]
        face='#ECF2FA' if kind=='data' else 'white'
        if kind=='stop': face='#FBECEC'; color='#B64E4E'
        if kind=='gate':
            ax.add_patch(Polygon([(x-w*.55,y),(x,y+h*.73),(x+w*.55,y),(x,y-h*.73)],
                                  facecolor='#FFF8E9',edgecolor=color,lw=.85,zorder=3))
        else:
            ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.002,rounding_size=0.004',
                         facecolor=face,edgecolor=color,lw=.8,zorder=3))
        ax.text(x,y,label,fontsize=fs,ha='center',va='center',color='#183047',zorder=4,linespacing=1.13)
    ax.text(.50,.108,'NEXT FEASIBLE RECIPE → robot submission',ha='center',fontsize=fs-1,color='#2456A0',
            bbox=dict(facecolor='white',edgecolor='none',pad=1))
    ax.text(.022,.076,'SOLID: control / physical sequence    DASHED GREY: data    DASHED RED: failure    DASHED GOLD: recovery',
            fontsize=fs-1.4,color='#526477')
    ax.text(.022,.052,'Current path: both analysis branches enabled; raw-image vision; double_explore; additive = 0 wt%. Hardware preparation forks run concurrently;',
            fontsize=fs-1.7,color='#526477')
    ax.text(.022,.032,'analysis branches dispatch sequentially. Validation repeats are prompt-directed. Pore fraction is the fitted compression changepoint, not a separate imaging measurement.',
            fontsize=fs-1.7,color='#526477')
    for ext in ['svg','pdf','png']:
        fig.savefig(OUT/(name+'.'+ext),dpi=300,facecolor='white')
    plt.close(fig)


if __name__=='__main__':
    plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none','pdf.fonttype':42})
    render('nips_workflow_detailed_paper',(11.69,8.27))
    render('nips_workflow_detailed_slide',(16,9),True)
    print('Rendered detailed graph: {} nodes, {} connections'.format(len(NODES),len(EDGES)))
