"""Build reproducible figures and a report from successful real C1 runs only."""
import argparse
import html
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

LABELS=['M1 · Exata','M2 · BM25S','M3 · Trigramas','M4 · Levenshtein','M5 · Splink']
COLORS=['#176c58','#2868a5','#d49b28','#b35b45','#8459a0']


def publish(root):
    root=Path(root);summaries=[];runs=[]
    for method in ('m1','m2','m3','m4','m5'):
        s=json.loads((root/method/'summary.json').read_text(encoding='utf-8'))
        rows=[json.loads(l) for l in (root/method/'per-query.jsonl').read_text(encoding='utf-8').splitlines()]
        if s['kind']!='real_c1_retrieval_measurement' or s['overall']['failures']:
            raise ValueError(f'{method}: failed or non-real run cannot enter this report')
        if len(rows)!=s['overall']['queries']:raise ValueError('Incomplete per-query file')
        if any(len(r['query_ms'])!=s['repetitions'] for r in rows):raise ValueError('Missing repetition')
        if any(len({h['entity_id'] for h in r['ranking']})!=len(r['ranking']) for r in rows):
            raise ValueError('Duplicate retrieval IDs')
        summaries.append(s);runs.append(rows)
    ids=[r['query_id'] for r in runs[0]]
    if any([r['query_id'] for r in rows]!=ids for rows in runs):raise ValueError('Different query cohorts')
    for rows in runs[1:]:
        if any(r['gold']!=base['gold'] for r,base in zip(rows,runs[0])):raise ValueError('Different qrels')
    # Cluster resampling keeps repeated queries about the same gold identity together.
    groups={}
    for i,r in enumerate(runs[0]):groups.setdefault(tuple(sorted(r['gold'])),[]).append(i)
    clusters=list(groups.values());rng=np.random.default_rng(42)
    samples=rng.integers(0,len(clusters),size=(10000,len(clusters)))
    counts=np.array([len(g) for g in clusters]);denom=counts[samples].sum(axis=1)
    cis={};paired={}
    for metric in ('hit@1','mrr@10','recall@20','ndcg@10'):
        values=np.array([[r['metrics'][metric] for r in rows] for rows in runs])
        sums=np.array([[v[g].sum() for g in clusters] for v in values])
        means=sums[:,samples].sum(axis=2)/denom
        cis[metric]=np.quantile(means,[.025,.975],axis=1).T.tolist()
        paired[metric]=np.quantile(means-means[0],[.025,.975],axis=1).T.tolist()
    output={'query_count':len(ids),'identity_clusters':len(clusters),'bootstrap_seed':42,
        'bootstrap_samples':10000,'confidence_level':.95,'intervals':cis,'paired_difference_vs_m1':paired,
        'interpretation':'Intervals describe this selected clean-identity cohort, not representativeness of user traffic.'}
    (root/'statistics.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    figures=root/'figures';figures.mkdir(exist_ok=True)
    x=np.arange(5)
    fig,axs=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    for ax,key,title in ((axs[0,0],'hit@1','Acerto na primeira posição'),(axs[0,1],'recall@20','Recall@20')):
        vals=np.array([s['overall']['quality'][key]*100 for s in summaries]);bounds=np.array(cis[key])*100
        ax.bar(x,vals,color=COLORS)
        ax.errorbar(x,vals,yerr=np.maximum(0,np.array([vals-bounds[:,0],bounds[:,1]-vals])),fmt='none',ecolor='#222',capsize=4)
        ax.set_ylim(0,105);ax.set_ylabel('%');ax.set_title(title+' · IC bootstrap 95%')
        for i,v in enumerate(vals):ax.text(i,v+1,f'{v:.2f}',ha='center',fontsize=9)
    vals=[s['overall']['latency_ms']['p95'] for s in summaries]
    axs[1,0].bar(x,vals,color=COLORS);axs[1,0].set_yscale('log');axs[1,0].set_ylabel('ms · escala log')
    axs[1,0].set_title('Latência p95 · chamada local, sem parsing')
    for i,v in enumerate(vals):axs[1,0].text(i,v*1.08,f'{v:.2f}',ha='center')
    vals=[s['peak_python_rss_bytes']/2**20 for s in summaries]
    axs[1,1].bar(x,vals,color=COLORS);axs[1,1].set_ylabel('MiB');axs[1,1].set_title('Pico RSS do Python · PostgreSQL excluído')
    for ax in axs.flat:ax.set_xticks(x,LABELS,rotation=18,ha='right');ax.grid(axis='y',alpha=.15)
    fig.suptitle(f'LopsIR · C1 · {len(ids)} consultas reais/derivadas de identidades reais\n341.827 entidades · 3 repetições · sem consultas fictícias',fontsize=13)
    for suffix in ('png','svg'):fig.savefig(figures/f'comparison.{suffix}',dpi=170)
    plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for col,collection in enumerate(('dispositivos','precedentes')):
        quality=[];latencies=[]
        for i,rows in enumerate(runs):
            subset=[r for r in rows if r['collection']==collection]
            times=[t for r in subset for t in r['query_ms']]
            hit=np.mean([r['metrics']['hit@1'] for r in subset])*100
            quality.append(hit);latencies.append(np.quantile(times,.95))
        for row,values in enumerate((quality,latencies)):
            ax=axes[row,col];ax.bar(x,values,color=COLORS);ax.set_xticks(x,[f'M{i}' for i in range(1,6)])
            ax.grid(axis='y',alpha=.15)
            for i,v in enumerate(values):ax.text(i,v+(1 if row==0 else v*.08),f'{v:.2f}',ha='center',fontsize=9)
            if row==0:ax.set_ylim(0,106);ax.set_title(f'{collection} · {len(subset)} consultas');ax.set_ylabel('Hit@1 (%)')
            else:ax.set_yscale('log');ax.set_ylabel('p95 local (ms, log)')
    fig.suptitle('C1 por coleção · mesmas consultas para os cinco métodos')
    for suffix in ('png','svg'):fig.savefig(figures/f'by-collection.{suffix}',dpi=170)
    plt.close(fig)
    lines=['# Resultados reais de C1 — primeira rodada','',
        'Fonte: acervo local de [leis-mcp](https://github.com/lops-legal/leis-mcp). '
        '358.448 registros físicos: 347.195 dispositivos legais e 11.253 precedentes. '
        'Deduplicação de identidade: 341.827 entidades. **Não são 370 mil acórdãos.**','',
        '**305 consultas de teste**, as mesmas para os cinco métodos: 7 chamadas estruturadas já existentes '
        'nos testes da fonte e 298 consultas derivadas exclusivamente de campos reais de identidade. '
        '95 consultas em treino e 107 em desenvolvimento. Nenhum caso jurídico fictício, nenhuma adulteração de referência.','',
        '| Método | Hit@1 | MRR@10 | Recall@20 | nDCG@10 | p50 ms | p95 ms | p99 ms | Preparo s | RSS Python MiB |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for label,s in zip(LABELS,summaries):
        q=s['overall']['quality'];t=s['overall']['latency_ms']
        lines.append(f"| {label} | {q['hit@1']:.4%} | {q['mrr@10']:.4f} | {q['recall@20']:.4%} | {q['ndcg@10']:.4f} | {t['p50']:.3f} | {t['p95']:.3f} | {t['p99']:.3f} | {s['prepare_seconds']:.2f} | {s['peak_python_rss_bytes']/2**20:.1f} |")
    lines+=['','![Comparação dos métodos](figures/comparison.png)','',
        '![Separação por coleção](figures/by-collection.png)','',
        '## O que estes números permitem concluir','',
        'A busca exata é a referência operacional para identidades estruturadas e íntegras deste lote. '
        'O positivo das consultas derivadas é a própria identidade de origem; o positivo das chamadas parciais '
        'é o conjunto compatível com os campos fornecidos. Isso favorece naturalmente igualdade e não é avaliação '
        'cega de relevância semântica. Não extrapolar para C2/C3, identificadores digitados incorretamente ou referências ausentes.','',
        'BM25 e trigramas podem perder a função dos números na serialização: número de reedição e artigo '
        'podem trocar de posição e manter os mesmos tokens. Levenshtein sobre a referência inteira pode preferir '
        'uma referência curta incorreta quando a consulta omite o tipo. Os arquivos por consulta mostram os erros reais.','',
        'M5 usa bloqueio por coleção+número e parâmetros Fellegi–Sunter estimados em treino. '
        'Os níveis de discordância não observados em treino mantêm padrões da biblioteca. Seus scores não são '
        'probabilidades calibradas e o bloqueio não tolera erro no número. As tentativas operacionais malsucedidas '
        'estão em `../attempts/` e não entram nesta tabela.','',
        '## Medição e limites','',
        '- Cada método percorreu 305 consultas × 3 repetições = 915 chamadas; falhas finais: zero. '
        'As consultas e tempos foram registrados em `c1.query_audit` no PostgreSQL.',
        '- A latência inclui a chamada ao banco ou motor em processo, pontuação e limpeza de tabelas quando aplicável. '
        'Exclui parsing da entrada original, HTTP, fila de produção e escrita do próprio log de auditoria.',
        '- Os testes foram sequenciais em máquina compartilhada; não há isolamento de CPU nem carga concorrente controlada. '
        'QPS serial não representa capacidade em produção. Cache frio não foi controlado.',
        '- Preparo não é uma comparação homogênea de construção completa: M1 já possui índices da importação; '
        'M3 inclui construção GiST na primeira rodada; M2/M4 carregam dados; M5 exporta, materializa e treina.',
        '- RSS é apenas do processo Python; servidor PostgreSQL e cache do sistema ficam de fora. '
        'Tamanho dos índices e plano KNN real estão em `audit.json`.',
        '- ICs bootstrap por conjunto de identidade, 10.000 reamostragens, semente 42: `statistics.json`. '
        'São incertezas deste lote selecionado; 100% observado não demonstra perfeição universal.',
        '- Precisão@20 divide por 20 mesmo quando C1 tem apenas uma identidade relevante; '
        'portanto 5% pode ser compatível com resposta correta e completa. Hit@1 e Recall são mais interpretáveis aqui.',
        '- Recall@20 = fração das identidades corretas conhecidas encontrada nas primeiras 20 posições. '
        'Não é acurácia global nem precisão da lista.',
        '- Custo de API: US$ 0; chamadas: 0. Custo monetário local, consumo elétrico, SLA de atualização, '
        'taxa de falsa aceitação de inexistentes e tolerância a erros: não medidos, não presumidos nulos.','',
        '## Dados completos e reprodução','',
        'Cada pasta `m1`…`m5` contém `summary.json` e `per-query.jsonl`: campos reais, positivos, ranking, '
        'tempos individuais, versões, commit de código e parâmetros. Ver [execução](../../../docs/c1/EXECUCAO.md).','',
        '## Sete consultas já existentes na fonte','',
        '| Consulta | M1 Hit@1 | M2 Hit@1 | M3 Hit@1 | M4 Hit@1 | M5 Hit@1 |',
        '|---|---:|---:|---:|---:|---:|']
    for i,r in enumerate(runs[0]):
        if r['origin']=='existing_reference_test':
            scores=' | '.join(str(int(rows[i]['metrics']['hit@1'])) for rows in runs)
            lines.append(f"| {r['text']} | {scores} |")
    (root/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # A portable browser view; full evidence remains Markdown/JSON, no remote dependencies.
    body=''.join(f'<tr><td>{html.escape(label)}</td><td>{s["overall"]["quality"]["hit@1"]:.2%}</td><td>{s["overall"]["latency_ms"]["p95"]:.3f}</td></tr>' for label,s in zip(LABELS,summaries))
    page=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>LopsIR C1</title>
    <style>body{{font:17px system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#18332e}}img{{width:100%}}td,th{{padding:12px;border-bottom:1px solid #ccc}}table{{border-collapse:collapse}}</style>
    <h1>LopsIR Benchmark · C1</h1><p>305 consultas · 341.827 entidades reais · 5 métodos · 3 repetições</p>
    <p>Referências estruturadas e íntegras. Não mede busca semântica, erros de digitação ou capacidade concorrente.</p>
    <table><tr><th>Método</th><th>Hit@1</th><th>p95 ms</th></tr>{body}</table>
    <img src="figures/comparison.svg" alt="Qualidade, latência e memória"><img src="figures/by-collection.svg" alt="Resultados por coleção">
    <p>Dados, limitações e reprodução: <a href="README.md">relatório completo</a>.</p></html>'''
    (root/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps({'methods':5,'queries':len(ids),'figures':4}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='reports/c1/real')
    a=p.parse_args();publish(a.root)
