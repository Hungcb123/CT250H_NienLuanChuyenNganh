"""Package frozen model weights, reviewed seed bars and Java parity fixtures.

Offline build step only; production runs Java with no Python dependencies.
T+60/120 retain the existing experimental baseline and are frozen at the seed
cutoff, rather than refitted inside a production HTTP request.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from lightgbm import LGBMClassifier
import onnx
import onnxruntime as ort

from regime_shock_features import completed_shock_features
from regime_shock_native import ShockNativeBundle, shock_file_digest
from regime_shock_score_runtime import ShockScoreRuntime
from train_regime_v2 import load_market_data, build_feature_matrix, create_labels
from experiment_regime_ohlcv import load_consensus
from onnx_tree_export import convert_lightgbm_float32


def prepare_onnx_deployment(argv=None):
    root=Path(__file__).resolve().parent
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,default=root/'artifacts/regime_shock_onnx_20261020_deploy')
    args=parser.parse_args(argv)
    source=args.source_dir
    output=root.parent/'backend/src/main/resources/models/shock'
    fixtures=root.parent/'backend/src/test/resources/models'
    output.mkdir(parents=True,exist_ok=True); fixtures.mkdir(parents=True,exist_ok=True)
    contract=json.loads((source/'contract.json').read_text())
    for name in ['shock_regime.onnx','contract.json','parity_fixture.json']:
        shutil.copyfile(source/name,output/name)
    data=root/'data/research/brokers_2010_20261001_reviewed'
    index,_=load_market_data(data/'VNINDEX.csv');etf,_=load_market_data(data/'E1VFVN30.csv')
    consensus,_=load_consensus(data,index)
    def number(value):return float(value) if np.isfinite(value) else None
    bars=[]
    for row in consensus.itertuples():
        bars.append(dict(date=str(row.Date.date()),close=float(row.Price),open=number(row.Open),
                         high=number(row.High),low=number(row.Low),volume=number(row.Volume)))
    seed=dict(schema=1,index=bars,etf=[dict(date=str(row.Date.date()),close=float(row.Price),
              volume=number(row.Volume),open=None,high=None,low=None) for row in etf.itertuples()],
              source_files={name:shock_file_digest(data/name) for name in ['VNINDEX.csv','E1VFVN30.csv','manifest.json']})
    (output/'market_seed.json').write_text(json.dumps(seed,separators=(',',':'),allow_nan=False)+'\n')
    frame,_=completed_shock_features(data)
    valid=np.isfinite(frame[contract['features']].to_numpy(dtype=float)).all(axis=1)
    rows=frame.loc[valid]
    feature_cases=[dict(session=str(row.Date.date()),features=[float(row[n]) for n in contract['features']],sigma=float(row.horizon_sigma)) for _,row in rows.iterrows()]
    (fixtures/'shock_feature_cases.json').write_text(json.dumps(feature_cases,separators=(',',':'))+'\n')
    # Native Python outputs at varied history points test raw bars -> Java
    # features -> Java ONNX, separately from already-engineered input fixtures.
    selected=rows.iloc[np.unique(np.linspace(0,len(rows)-1,32).astype(int))]
    bundle=ShockNativeBundle(root/'artifacts/regime_shock_candidate_20261019T090555_259289Z/native')
    parts=bundle.predict_components({n:selected[n].to_numpy() for n in contract['features']},selected.horizon_sigma.to_numpy())
    cases=[]
    for i,(_,row) in enumerate(selected.iterrows()):
        reference=ShockScoreRuntime('java-raw-parity').predict(str(row.Date.date()),None,{n:v[i] for n,v in parts.items()},contract['parameters'])
        cases.append(dict(session=reference['session'],class_scores=reference['class_scores'],signal=reference['signal']))
    (fixtures/'shock_raw_inference_cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    baseline,names=build_feature_matrix(index,etf,'close-etf')
    for horizon in [60,120]:
        train=create_labels(baseline,horizon,names)
        model=LGBMClassifier(n_estimators=180,num_leaves=15,max_depth=5,learning_rate=.03,
              min_child_samples=60,reg_lambda=2.,class_weight='balanced',random_state=42,n_jobs=2,
              verbosity=-1,deterministic=True,force_col_wise=True).fit(train[names],train.label)
        converted=convert_lightgbm_float32(model,len(names))
        converted.ir_version=8
        path=output/f'regime_t{horizon}.onnx';onnx.save(converted,path)
        x=baseline.loc[np.isfinite(baseline[names]).all(axis=1),names].to_numpy(dtype=np.float32)
        options=ort.SessionOptions();options.intra_op_num_threads=2
        session=ort.InferenceSession(str(path),options)
        actual=session.run([session.get_outputs()[1].name],{'input':x})[0];expected=model.predict_proba(x)
        np.testing.assert_allclose(actual,expected,atol=1e-5,rtol=0)
        np.testing.assert_array_equal(actual.argmax(axis=1),expected.argmax(axis=1))
        metadata=dict(horizon=horizon,features=names,boundary=str(index.Date.iloc[-1].date()),
                      experimental=True,validation_status='NOT_EVALUATED',training_rows=len(train),
                      max_label_end_date=str(train.label_end_date.max().date()),
                      parity_rows=len(x),max_absolute_error=float(np.abs(actual-expected).max()),
                      class_scores_are_probabilities=False,
                      fixture=dict(features=x[-1].tolist(),class_scores=expected[-1].tolist()))
        (output/f'regime_t{horizon}.json').write_text(json.dumps(metadata,indent=2)+'\n')
    checksums={p.name:shock_file_digest(p) for p in sorted(output.iterdir()) if p.name!='checksums.json'}
    (output/'checksums.json').write_text(json.dumps(checksums,indent=2)+'\n')
    print('Packaged Java ONNX models:',output)
    print('Raw feature parity cases:',len(feature_cases))


if __name__=='__main__':prepare_onnx_deployment()
