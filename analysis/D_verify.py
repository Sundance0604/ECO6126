"""Validate the generated data, splits, and saved numerical outputs."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parents[1]; O=R/'outputs/D'
d=pd.read_csv(R/'data/extensions/D/ml_dense_rho_p.csv')
assert len(d)==17280
assert not d.duplicated(['rho','p','seed','E']).any()
assert d.groupby(['rho','p','seed']).E.nunique().eq(2).all()
assert d.surv.between(1,200).all()
m=json.loads((O/'design.json').read_text()); assert m['configurations']==108
pred=pd.read_csv(O/'test_predictions.csv'); tab=pd.read_csv(O/'tables/Table3.csv')
assert pred.seed.between(65,80).all()
held=set(m['held_rho'])
for (protocol,name),z in pred.groupby(['protocol','model']):
 assert z.rho.isin(held).all() if protocol=='Unseen configurations' else not z.rho.isin(held).any()
 c=z.groupby(['rho','p'])[['delta','prediction']].mean()
 t=tab[(tab.protocol==protocol)&(tab.model==name)].iloc[0]
 assert np.isclose(np.mean(abs(c.delta-c.prediction)),t.cell_MAE)
 assert np.isclose(np.sqrt(np.mean((z.delta-z.prediction)**2)),t.paired_RMSE)
assert np.isfinite(tab.select_dtypes('number')).all().all()
print('PASS: 17,280 unique runs; complete pairs; seed/configuration separation; all 12 model scores recomputed.')

reference = pd.read_csv(R / 'data/extensions/D/task_a_reference.csv')
assert len(reference) == 800 and reference.B.eq(1).all()
keys = ['rho', 'p', 'E', 'seed']
overlap = reference.merge(d, on=keys, validate='one_to_one')
assert len(overlap) == len(reference)
assert overlap.rmst_T.eq(overlap.surv).all()
print('PASS: all 800 matched Task A baseline runs have identical restricted survival.')
