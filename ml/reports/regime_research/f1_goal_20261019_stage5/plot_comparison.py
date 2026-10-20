"""Standalone plot from completed reports; no model or coefficient selection."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
configs=[('Reference 51.34%', 'regime_magnitude_forest/20261019T070928_701705Z','magnitude_shrink'),
    ('Context: shrink','regime_information_forest/20261019T071622_321945Z','context_shrink'),
    ('Context: replace forests','regime_information_forest/20261019T071622_321945Z','context_forest_replace'),
    ('Combined context (diagnostic)','regime_information_forest/20261019T071622_321945Z','combined_context_diagnostic'),
    ('Analogs: 25% density','regime_analog_density/20261019T071721_721598Z','analog_shrink'),
    ('Analogs: 50% density','regime_analog_density/20261019T071721_721598Z','analog_half'),
    ('Shock: 25% density','regime_shock_forest/20261019T072038_455776Z','shock_shrink'),
    ('Shock: 50% density','regime_shock_forest/20261019T072038_455776Z','shock_half')]
values=[]
for label,directory,candidate in configs:
    report=json.loads((ROOT/'reports'/directory/'report.json').read_text())
    item=next(v for v in report['results'] if v['candidate']==candidate)
    values.append([f['f1_macro'] for f in item['folds']])
values=np.asarray(values)*100;rows=np.arange(len(values))
fig,ax=plt.subplots(figsize=(11,6))
for i in range(4):ax.scatter(values[:,i],rows,s=42,label=f'Fold {i+1}',zorder=3)
ax.scatter(values.mean(axis=1),rows,s=65,c='black',marker='D',label='Mean of 4 folds',zorder=4)
for i,row in enumerate(values):
    ax.hlines(i,row.min(),row.max(),color='#cccccc',linewidth=1,zorder=1)
    ax.annotate(f'{row.mean():.2f}%',(row.mean(),i),xytext=(0,-14),textcoords='offset points',ha='center',fontsize=9)
ax.set_yticks(rows,[v[0] for v in configs]);ax.invert_yaxis();ax.set_xlim(0,100)
ax.set_xlabel('Macro F1 (%) — fixed three classes; not accuracy')
ax.set_title('T+20: same 1,560 historical DEVELOPMENT dates\nRepeated research exposure; no independent test or deployment acceptance',fontsize=12)
ax.grid(axis='x',alpha=.18);ax.spines[['top','right']].set_visible(False)
ax.legend(loc='upper center',bbox_to_anchor=(.5,-.13),ncol=5,fontsize=9)
fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=180);plt.close(fig)
print(str(OUT/'comparison.png'))
