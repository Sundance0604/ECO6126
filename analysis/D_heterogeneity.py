#!/usr/bin/env python3
"""Task D: reproducible ML heterogeneity study. See outputs/D/README.md for estimands and splits."""
from pathlib import Path
import os
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('OMP_NUM_THREADS', '1')
import argparse, json, time, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.linear_model import LinearRegression
# Import the pinned Task A simulator and its recording adapter from the shared repository.
sys.path.insert(0, str(ROOT))
from src.market import MarketModel, Params

BASELINE = json.loads((ROOT / 'configs/baseline.json').read_text(encoding='utf-8'))
TASK_A_COMMIT = 'd30d156a1343a8261e83ff000e9fb13fe050445d'
MODEL_VERSION = 'v1.5-A-raw-4d85097a0e80'
BANKRUPTCY = True
OUT = ROOT / 'outputs/D'
FEATURES = ['rho', 'p']
HELD = {8, 13, 18, 23, 28, 33, 38}


def run_market(cfg):
    r, p, e, seed = cfg
    n = BASELINE['N']
    cheaters = round(n * r / 100)
    honest = n - cheaters
    horizon = BASELINE['T']
    params = Params(
        H=honest, C=cheaters, p=p, q=BASELINE['q'], a=BASELINE['a'],
        c=BASELINE['c'], w_init=BASELINE['w_init'], max_steps=horizon,
        seed=seed, enable_bankrupt=BANKRUPTCY, enable_evict=bool(e),
        **BASELINE['payoffs'],
    )
    market = MarketModel(params)
    survival = horizon
    while market.t < horizon:
        previous_step = market.t
        can_continue = market.step()
        if market.t == previous_step:
            break
        state = market.agg_history[-1]
        if 10 * state['H_active'] <= honest:
            survival = market.t
            break
        # With c=0 and no active cheaters, the honest population cannot fall.
        if not can_continue or (BASELINE['c'] == 0 and state['C_active'] == 0):
            break
    return dict(rho=r / 100, p=p, E=e, seed=seed, surv=float(survival))


def simulate(workers, force=False):
    path = ROOT/'data/extensions/D/ml_dense_rho_p.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(path) if path.exists() and not force else pd.DataFrame(columns=['rho','p','E','seed','surv'])
    df['r']=np.rint(df.rho*100).astype(int)
    df=df.drop_duplicates(['r','p','E','seed'])
    keys=set(map(tuple,df[['r','p','E','seed']].to_numpy()))
    cfg=[(r,p,e,s) for r in range(5,41) for p in [2,3,4] for e in [0,1] for s in range(1,81)]
    todo=[x for x in cfg if x not in keys]
    print(f'Simulation: {len(todo)} new runs; {len(keys)} cached',flush=True)
    rows=[]; t=time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for k,row in enumerate(pool.map(run_market,todo,chunksize=10),1):
            rows.append(row)
            if k%1000==0: print(f'  {k}/{len(todo)} runs, {time.time()-t:.0f}s',flush=True)
    if rows:
        df=pd.concat([df.drop(columns='r'),pd.DataFrame(rows)],ignore_index=True)
    else: df=df.drop(columns='r')
    df=df.sort_values(['rho','p','seed','E']).reset_index(drop=True)
    df.to_csv(path,index=False)
    return df


def paired(d):
    t=d.pivot(index=['rho','p','seed'],columns='E',values='surv').reset_index()
    assert t[[0,1]].notna().all().all()
    t['delta']=t[1]-t[0]
    return t


def basis(x, kind, cut=.225):
    r,p=np.asarray(x).T
    if kind=='OLS interaction': return np.c_[r,p,r*p]
    if kind=='OLS quadratic': return np.c_[r,p,r*p,r*r,p*p]
    return np.c_[r,p,r*p,r>=cut,p*(r>=cut)]


class Estimator:
    def __init__(self,name,setting): self.name,self.setting=name,setting
    def fit(self,d):
        pairs=paired(d); x=pairs[FEATURES].to_numpy(); y=pairs.delta.to_numpy()
        if self.name.startswith('OLS') or self.name=='Segmented regression':
            self.model=LinearRegression().fit(basis(x,self.name,self.setting),y)
        elif self.name=='Random Forest':
            self.model=RandomForestRegressor(n_estimators=200,min_samples_leaf=self.setting,max_features=1.,random_state=712,n_jobs=1).fit(x,y)
        elif self.name=='Gradient Boosting':
            self.model=HistGradientBoostingRegressor(max_iter=160,max_leaf_nodes=self.setting,learning_rate=.06,min_samples_leaf=15,l2_regularization=1.,random_state=712).fit(x,y)
        else:
            x=d[FEATURES].to_numpy(); y=d.surv.to_numpy(); e=d.E.to_numpy()
            nuisance=HistGradientBoostingRegressor(max_iter=120,max_leaf_nodes=7,min_samples_leaf=20,random_state=712)
            m=cross_val_predict(nuisance,x,y,groups=d.seed,cv=GroupKFold(4))
            # R loss weights (E-.5)^2=.25 are constant in this balanced design.
            pseudo=(y-m)/(e-.5)
            self.model=HistGradientBoostingRegressor(max_iter=160,max_leaf_nodes=self.setting,learning_rate=.06,min_samples_leaf=30,l2_regularization=1.,random_state=712).fit(x,pseudo)
        return self
    def predict(self,x):
        a=np.asarray(x)
        if self.name.startswith('OLS') or self.name=='Segmented regression': a=basis(a,self.name,self.setting)
        return self.model.predict(a)


def score(pred):
    c=pred.groupby(FEATURES)[['delta','prediction']].mean()
    return {'cell_MAE':float(np.mean(abs(c.delta-c.prediction))), 'cell_RMSE':float(np.sqrt(np.mean((c.delta-c.prediction)**2))), 'paired_RMSE':float(np.sqrt(np.mean((pred.delta-pred.prediction)**2)))}


def predict_frame(model,d):
    z=paired(d); z['prediction']=model.predict(z[FEATURES]); return z


def bootstrap_metric(z,reps=300):
    rng=np.random.default_rng(198); seeds=z.seed.unique(); vals=[]
    for _ in range(reps):
        counts=pd.Series(rng.choice(seeds,len(seeds),replace=True)).value_counts()
        q=z.copy(); q['w']=q.seed.map(counts).fillna(0)
        q['yd']=q.delta*q.w; q['yp']=q.prediction*q.w
        c=q.groupby(FEATURES)[['yd','yp','w']].sum()
        vals.append(np.mean(abs((c.yd-c.yp)/c.w)))
    return (*np.quantile(vals,[.025,.975]), float(np.std(vals, ddof=1)))


def analyze(d):
    for subdir in ("figures", "tables"):
        (OUT / subdir).mkdir(parents=True, exist_ok=True)
    held=np.rint(d.rho*100).astype(int).isin(HELD)
    train=d[(d.seed<=48)&~held]; val=d[d.seed.between(49,64)&~held]
    tests={'New seeds':d[(d.seed>=65)&~held], 'Unseen configurations':d[(d.seed>=65)&held]}
    assert not set(train.seed)&set(val.seed)
    assert not set(train.seed)&set(tests['New seeds'].seed)
    assert not set(map(tuple,train[FEATURES].to_numpy()))&set(map(tuple,tests['Unseen configurations'][FEATURES].to_numpy()))
    settings={'OLS interaction':[0], 'OLS quadratic':[0], 'Segmented regression':[.125,.175,.225,.275,.325], 'Random Forest':[5,20,40], 'Gradient Boosting':[7,15], 'R-learner':[7,15]}
    tuning=[]; models={}; results=[]; predictions=[]
    for name,opts in settings.items():
        best=None
        for opt in opts:
            m=Estimator(name,opt).fit(train); metric=score(predict_frame(m,val))['cell_MAE']
            tuning.append(dict(model=name,setting=opt,validation_cell_MAE=metric))
            if best is None or metric<best[0]: best=(metric,opt)
        models[name]=Estimator(name,best[1]).fit(pd.concat([train,val]))
        print(f'{name}: selected {best[1]}, validation MAE {best[0]:.3f}',flush=True)
        for protocol,test in tests.items():
            z=predict_frame(models[name],test); metrics=score(z); lo,hi,sd=bootstrap_metric(z)
            results.append(dict(protocol=protocol,model=name,setting=best[1],**metrics,MAE_boot_P025=lo,MAE_boot_P975=hi,MAE_boot_SD=sd))
            z['model']=name; z['protocol']=protocol; predictions.append(z)
    table=pd.DataFrame(results); table.to_csv(OUT/'tables/Table3.csv',index=False)
    pd.DataFrame(tuning).to_csv(OUT/'validation_tuning.csv',index=False)
    pd.concat(predictions).to_csv(OUT/'test_predictions.csv',index=False)
    # Select primary ML method using validation only, never test performance.
    tune=pd.DataFrame(tuning); ml=tune[tune.model.isin(['Random Forest','Gradient Boosting','R-learner'])]
    primary=ml.loc[ml.validation_cell_MAE.idxmin(),'model']; model=models[primary]
    print(f'Primary ML method (validation selection): {primary}',flush=True)
    grid=pd.DataFrame([(r/100,p) for p in [2,3,4] for r in range(5,41)],columns=FEATURES)
    for name,m in models.items(): grid[name]=m.predict(grid[FEATURES])
    grid.to_csv(OUT/'cate_grid.csv',index=False)
    testall=d[d.seed>=65]; obs=paired(testall).groupby(FEATURES).delta.agg(['mean','std','count']).reset_index()
    obs['se']=obs['std']/np.sqrt(obs['count']); obs.to_csv(OUT/'test_cell_effects.csv',index=False)
    # Thresholds are operational cutoffs, not statistically identified change points.
    boundaries=[]
    for p in [2,3,4]:
        g=grid[grid.p==p].sort_values('rho')
        for threshold in [25,50,100]:
            effective=g[primary].to_numpy()>threshold
            cross=np.where(effective[:-1]&~effective[1:])[0]
            boundaries.append(dict(p=p,threshold_steps=threshold,last_effective_rho=float(g.rho.iloc[cross[0]]) if len(cross) else np.nan,first_ineffective_rho=float(g.rho.iloc[cross[0]+1]) if len(cross) else np.nan,downward_crossings=len(cross),status='bracketed' if len(cross) else ('all_effective' if effective.all() else 'no_downward_crossing')))
    # Independent test-grid crossing and seed-bootstrap variability of its location.
    testpairs=paired(testall)
    rng_boundary=np.random.default_rng(771)
    for row in boundaries:
        z=testpairs[testpairs.p==row['p']].pivot(index='rho',columns='seed',values='delta').sort_index()
        rhos=z.index.to_numpy(); values=z.to_numpy(); threshold=row['threshold_steps']
        def crossing(v):
            ix=np.where((v[:-1]>threshold)&(v[1:]<=threshold))[0]
            return float(rhos[ix[0]]) if len(ix) else np.nan
        row['test_last_effective_rho']=crossing(values.mean(axis=1))
        boot=[crossing(values[:,rng_boundary.integers(0,values.shape[1],values.shape[1])].mean(axis=1)) for _ in range(300)]
        finite=np.array(boot)[np.isfinite(boot)]
        row['test_crossing_boot_low']=float(np.quantile(finite,.025)) if len(finite) else np.nan
        row['test_crossing_boot_high']=float(np.quantile(finite,.975)) if len(finite) else np.nan
        row['test_boot_no_crossing_fraction']=1-len(finite)/300
    pd.DataFrame(boundaries).to_csv(OUT/'critical_regions.csv',index=False)
    # Held-out loss permutation importance: increase in cell-level MAE, no causal shares.
    imp=[]; rng=np.random.default_rng(901)
    for protocol,test in tests.items():
        z=paired(test).groupby(FEATURES).delta.mean().reset_index(); x=z[FEATURES].to_numpy(); y=z.delta.to_numpy(); base=np.mean(abs(y-model.predict(x)))
        for j,f in enumerate(FEATURES):
            inc=[]
            for _ in range(100):
                xp=x.copy(); xp[:,j]=rng.permutation(xp[:,j]); inc.append(np.mean(abs(y-model.predict(xp)))-base)
            imp.append(dict(protocol=protocol,feature=f,MAE_increase=float(np.mean(inc)),permutation_sd=float(np.std(inc))))
    pd.DataFrame(imp).to_csv(OUT/'feature_importance.csv',index=False)
    meta=dict(primary_model=primary,runs=len(d),configurations=108,train_runs=len(train),validation_runs=len(val),test_runs={k:len(v) for k,v in tests.items()},train_seeds=[1,48],validation_seeds=[49,64],test_seeds=[65,80],held_rho=sorted(r/100 for r in HELD),test_bootstrap='Seed bootstrap SD and percentile distribution of fixed-model errors; excludes training uncertainty, not confidence intervals',features=FEATURES)
    meta.update(task_a_commit=TASK_A_COMMIT, model_version=MODEL_VERSION,
                B=int(BANKRUPTCY), q=BASELINE['q'], c=BASELINE['c'],
                T=BASELINE['T'], outcome='Task A rmst_T, stored as surv')
    (OUT/'design.json').write_text(json.dumps(meta,indent=2))
    plot(grid,obs,table,pd.DataFrame(imp),primary)
    lines=['# Table 3 Out of sample CATE comparison','', '| Test | Model | Cell MAE | Cell RMSE | Paired RMSE | MAE bootstrap SD |','|---|---|---:|---:|---:|---|']
    for r in table.itertuples(): lines.append(f'| {r.protocol} | {r.model} | {r.cell_MAE:.2f} | {r.cell_RMSE:.2f} | {r.paired_RMSE:.2f} | {r.MAE_boot_SD:.2f} |')
    lines+=['','Bankruptcy is enabled (B = 1), q = 3, and the outcome is restricted survival through T = 200. Cell errors compare predictions with independent test seed mean paired effects. Paired RMSE includes individual simulation noise. Bootstrap SD resamples the 16 test seeds for a fixed fitted model; it excludes training uncertainty. Percentile ranges in the CSV describe the bootstrap distribution and are not confidence intervals for population prediction error. Hyperparameters and the primary ML model are selected exclusively on validation seeds.']
    (OUT/'tables/Table3.md').write_text('\n'.join(lines))
    print(table.to_string(index=False),flush=True)


def plot(grid,obs,table,imp,primary):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.bbox':'tight'})
    colors=['#D55E00','#0072B2','#009E73']
    fig,axs=plt.subplots(1,3,figsize=(13.5,4),sharey=True)
    for ax,p,c in zip(axs,[2,3,4],colors):
        g=grid[grid.p==p]; o=obs[obs.p==p]
        for name,ls in [('Random Forest','--'),('Gradient Boosting','-.'),('R-learner','-')]: ax.plot(g.rho,g[name],ls,label=name,lw=1.6)
        ax.errorbar(o.rho,o['mean'],yerr=1.96*o.se,fmt='o',ms=2.8,color=c,alpha=.65,label='Independent test means')
        ax.axhline(50,color='gray',ls=':',lw=1); ax.set(title=f'p = {p}',xlabel='Initial cheater share rho',xlim=(.045,.405))
        for r in sorted(HELD): ax.axvspan(r/100-.002,r/100+.002,color='gray',alpha=.13)
    fig.suptitle('Expulsion effects with bankruptcy enabled (B = 1, q = 3)')
    axs[0].set_ylabel('Effect on restricted survival (steps)'); axs[0].legend(fontsize=7,loc='lower left')
    fig.tight_layout(); fig.savefig(OUT/'figures/Figure3.png',dpi=240); fig.savefig(OUT/'figures/Figure3.pdf'); plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.5,3.5)); q=imp[imp.protocol=='Unseen configurations']
    ax.bar(q.feature,q.MAE_increase,color=colors[:2]); ax.set(ylabel='Increase in held-out cell MAE (steps)',title=f'Permutation importance: {primary}')
    fig.tight_layout(); fig.savefig(OUT/'figures/feature_importance.png',dpi=220); plt.close(fig)


if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--workers',type=int,default=8); ap.add_argument('--force',action='store_true'); ap.add_argument('--analyze',action='store_true'); a=ap.parse_args()
    d=pd.read_csv(ROOT/'data/extensions/D/ml_dense_rho_p.csv') if a.analyze else simulate(a.workers,a.force)
    analyze(d)
