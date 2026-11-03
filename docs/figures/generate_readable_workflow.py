"""Readable intermediate-detail NIPS flowchart: Python + Matplotlib only."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon

OUT=Path(__file__).resolve().parent
COLORS=['#365F94','#00847E','#B37326','#7955A0']
# Lane, row, short title, short operational detail.
NODES={
 'setup':(0,0,'Set campaign context','Materials + bath composition'),
 'history':(0,1,'Load experimental history','Filtered warm-start records'),
 'seed':(0,2,'Select first recipe','Warm-start LLM or initial recipe'),
 'validate':(0,3,'Validate recipe','JSON schema + locks + stocks'),
 'send':(0,4,'Submit to robot','Health / journal → POST /run'),
 'state':(0,5,'Checkpoint each stage','Resume incomplete processing'),
 'prep':(1,0,'Prepare in parallel','Cool bath · zero coupon · mix dope'),
 'cast':(1,1,'Dispense & blade cast','OT-2 dosing → xArm casting'),
 'expose':(1,2,'Expose cast film','Dry N₂ or ambient wait'),
 'bath':(1,3,'Form membrane in baths','NIPS hold → 45 min second bath'),
 'pre':(1,4,'Capture pre-test image','xArm → enclosed camera station'),
 'test':(1,5,'Compression + final image','4 sample curves · post-test photo'),
 'archive':(2,0,'Archive completed run','4 zero + 4 sample CSVs; 2 photos'),
 'branch':(2,1,'Dispatch analysis branches','Mechanics first; image branch next'),
 'mechanics':(2,2,'Correct mechanical curves','Zero subtraction → stress–strain'),
 'fit':(2,3,'Fit & extract properties','GAM + regional fits; fit checks'),
 'vision':(2,4,'Assess pre-test photograph','Vision LLM: coverage + defects'),
 'merge':(2,5,'Combine run outcomes','Properties ± SD + quality report'),
 'memory':(3,0,'Update experimental memory','Live + warm history; bath context'),
 'choose':(3,1,'Recommend next experiment','Modulus + pore fraction objectives'),
 'policy':(3,2,'Explore or validate candidate','Prompt requests independent repeats'),
 'json':(3,3,'Validate next-recipe JSON','Locks + stock-feasible composition'),
 'submit':(3,4,'Save & submit next run','Checkpoint → health → robot'),
 'review':(3,5,'Review campaign offline','Fit / quality logs; repeatability'),
}

def render(name,size,slide=False):
 fig=plt.figure(figsize=size,facecolor='white')
 ax=fig.add_axes([0,0,1,1]); ax.set(xlim=(0,1),ylim=(0,1)); ax.axis('off')
 fs=12 if slide else 8
 xs=[.125,.375,.625,.875]; ys=[.795-.119*i for i in range(6)]
 w,h=.211,.073
 ax.text(.025,.972,'NIPS membrane discovery: robotic workflow and learning loop',fontsize=19 if slide else 12.5,
         color='#183047',weight='bold',va='top')
 ax.text(.025,.925,'Four zero curves + four sample curves per run  •  Hardware, analysis and experimental decisions',
         fontsize=fs,color='#526477',va='top')
 for i,t in enumerate(['CAMPAIGN CONTROL','ROBOTIC FABRICATION','CHARACTERIZATION','LEARNING & VALIDATION']):
  ax.add_patch(FancyBboxPatch((i*.25+.008,.148),.234,.727,boxstyle='round,pad=0.002',facecolor=COLORS[i],alpha=.045,edgecolor='none'))
  ax.text(xs[i],.854,t,ha='center',fontsize=fs,color=COLORS[i],weight='bold')
 def coord(key):
  c,r,_,_=NODES[key]; return xs[c],ys[r]
 def edge(a,b,kind='normal',route=None):
  x,y=coord(a); xx,yy=coord(b)
  color={'data':'#8897A6','feedback':'#2456A0','branch':'#926130'}.get(kind,'#526D7A')
  ls='--' if kind=='data' else '-'
  if route=='bottom':
   pts=[(x+w/2,y),(.992,y),(.992,.126),(.008,.126),(.008,yy),(xx-w/2,yy)]
  elif route=='top':
   pts=[(x+w/2,y),(x+w/2+.008,y),(x+w/2+.008,.885),(xx-w/2-.008,.885),(xx-w/2-.008,yy),(xx-w/2,yy)]
  elif abs(x-xx)<.01:
   if abs(y-yy)<.13:
    sign=1 if yy>y else -1; pts=[(x,y+sign*h/2),(xx,yy-sign*h/2)]
   else:
    g=x-w/2-.008
    pts=[(x-w/2,y),(g,y),(g,yy),(xx-w/2,yy)]
  else:
   mid=(x+xx)/2
   pts=[(x+w/2,y),(mid,y),(mid,yy),(xx-w/2,yy)]
  ax.plot([p[0] for p in pts],[p[1] for p in pts],c=color,lw=1 if kind!='feedback' else 1.6,ls=ls,zorder=1)
  ax.add_patch(FancyArrowPatch(pts[-2],pts[-1],arrowstyle='-|>',mutation_scale=8,color=color,lw=1,ls=ls,zorder=1))
 for keys in [ ['setup','history','seed','validate','send'],['prep','cast','expose','bath','pre','test'],
               ['archive','branch','mechanics','fit'],['memory','choose','policy','json','submit'] ]:
  for a,b in zip(keys,keys[1:]): edge(a,b)
 edge('send','prep')
 edge('test','archive')
 edge('branch','vision','branch')
 edge('fit','merge','branch')
 edge('vision','merge','branch')
 edge('merge','memory',route='top')
 edge('submit','send','feedback','bottom')
 edge('merge','review','data')
 edge('send','state','data')
 for key,(c,r,title,detail) in NODES.items():
  x,y=coord(key)
  ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.003,rounding_size=0.007',
                 facecolor='white',edgecolor=COLORS[c],lw=1,zorder=3))
  ax.text(x,y+.012,title,fontsize=fs,weight='bold',ha='center',va='center',color='#183047',zorder=4)
  ax.text(x,y-.016,detail,fontsize=fs-1.4,ha='center',va='center',color='#526477',zorder=4)
 ax.text(.5,.126,'NEXT FEASIBLE RECIPE',ha='center',va='center',fontsize=fs-1,color='#2456A0',
         bbox=dict(facecolor='white',edgecolor='none',pad=2))
 ax.text(.025,.078,'Preparation includes xArm coupon handling + 4 zero tests, bath chilling, and OT-2 preparation of 1000 µL casting dope.',fontsize=fs-1.2,color='#526477')
 ax.text(.025,.051,'Compression uses Arduino Uno triggering, Newton CSVs and LVDT safety / freshness checks. Pore fraction = fitted changepoint strain.',fontsize=fs-1.2,color='#526477')
 ax.text(.025,.024,'Solid arrows: process / dependency  ·  Dashed arrows: records / offline review  ·  Independent synthesis repeats are requested through the LLM prompt.',fontsize=fs-1.5,color='#526477')
 for ext in ['pdf','svg','png']: fig.savefig(OUT/(name+'.'+ext),dpi=300,facecolor='white')
 plt.close(fig)

if __name__=='__main__':
 plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none','pdf.fonttype':42})
 render('nips_workflow_readable_paper',(180/25.4,150/25.4))
 render('nips_workflow_readable_slide',(16,9),True)
 print('Rendered readable workflow: 24 bricks, paper and slide.')
