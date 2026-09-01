from core.data_loader import load_nodes, load_hourly_parameters, load_tasks, load_baseline_results
from core.solver import solve_dispatch

def main():
    nodes=load_nodes(); hourly=load_hourly_parameters(); tasks=load_tasks()
    sol=solve_dispatch(nodes,hourly,tasks,carbon_weight=0.25,objective_mode='balanced',time_limit=5.0)
    s=sol['summary']
    ref=load_baseline_results().loc[lambda x:x['方案']=='电碳算协同MILP'].iloc[0]
    print('dynamic:', {k: round(s[k],4) for k in ['cash_cost','dispatch_carbon','location_carbon','market_carbon','completion_rate','sla_rate','green_share']})
    print('reference:', round(ref['现金成本_CNY'],4), round(ref['调度碳代理_kgCO2'],4), round(ref['位置法碳排_kgCO2'],4), round(ref['市场法碳排_kgCO2'],4))
    assert abs(s['cash_cost']-ref['现金成本_CNY']) < 1e-3
    assert abs(s['dispatch_carbon']-ref['调度碳代理_kgCO2']) < 1e-3
    assert s['completion_rate'] > 99.999 and s['sla_rate'] > 99.999
    print('SMOKE TEST PASSED')
if __name__=='__main__': main()
