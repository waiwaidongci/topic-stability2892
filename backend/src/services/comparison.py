import numpy as np
from scipy.optimize import linear_sum_assignment
from src.constants.comparison import RULE_VERSION,EVIDENCE_TERMS,DIFF_TERMS

def _reference_topics(run_result):
 # 参照分解（第0次拟合）的H行就是冻结的主题词权，行序即主题编号；
 # 同时从 profile 取人工主题名（名称属于编辑判断，不参与数值匹配）。
 vocabulary=run_result['vocabulary']
 reference=run_result['replicates'][0]
 H=np.asarray(reference['H'],dtype=float)
 profiles=run_result.get('profiles',[])
 topics=[]
 for i,row_weights in enumerate(H):
  profile=next((p for p in profiles if p['topic_index']==i),None)
  topics.append({'topic_index':i,'label':(profile or {}).get('label',f'待命名主题{i+1:02d}'),
                 'editor_note':(profile or {}).get('editor_note',''),
                 'weights':{vocabulary[j]:float(row_weights[j]) for j in range(len(vocabulary)) if row_weights[j]>0.0}})
 return vocabulary,topics

def build_term_aligned(run_a,run_b):
 vocab_a,topics_a=_reference_topics(run_a.result)
 vocab_b,topics_b=_reference_topics(run_b.result)
 union=sorted(set().union(*(set(t['weights']) for t in topics_a),*(set(t['weights']) for t in topics_b)))
 if not union:raise ValueError('两个任务的词权均为空，无法按词项对齐')
 index={term:i for i,term in enumerate(union)}
 def vectors(topics):
  V=np.zeros((len(topics),len(union)))
  for r,t in enumerate(topics):
   for term,w in t['weights'].items():V[r,index[term]]=w
   scale=V[r].sum()
   if scale>1e-14:V[r]/=scale
  return V
 Va=vectors(topics_a);Vb=vectors(topics_b)
 only_a=sorted(set(vocab_a)-set(vocab_b));only_b=sorted(set(vocab_b)-set(vocab_a))
 shared=sorted(set(vocab_a)&set(vocab_b))
 return {'union_terms':union,'Va':Va,'Vb':Vb,'topics_a':topics_a,'topics_b':topics_b,
         'vocab_a':vocab_a,'vocab_b':vocab_b,'shared_terms':shared,'only_a':only_a,'only_b':only_b}

def _cosine_matrix(Va,Vb):
 na=np.linalg.norm(Va,axis=1);nb=np.linalg.norm(Vb,axis=1)
 if (na<=1e-14).any() or (nb<=1e-14).any():raise ValueError('对齐后出现空主题向量，不能计算相似度')
 cosine=np.clip((Va/na[:,None])@(Vb/nb[:,None]).T,0,1)
 return cosine

def _term_evidence(ta,tb,union,Va_row,Vb_row):
 # 匹配依据：各自高词权词、共享词上的词权对照，以及只在一侧出现的差异词。
 order_a=np.argsort(-Va_row,kind='stable');order_b=np.argsort(-Vb_row,kind='stable')
 top_a=[{'term':union[int(i)],'weight':float(Va_row[i])} for i in order_a[:EVIDENCE_TERMS] if Va_row[i]>0]
 top_b=[{'term':union[int(i)],'weight':float(Vb_row[i])} for i in order_b[:EVIDENCE_TERMS] if Vb_row[i]>0]
 shared_rows=[]
 for term in sorted(set(ta['weights'])&set(tb['weights'])):
  wa=ta['weights'].get(term,0.0);wb=tb['weights'].get(term,0.0)
  shared_rows.append({'term':term,'weight_a':float(wa),'weight_b':float(wb),'gap':float(abs(wa-wb))})
 shared_rows.sort(key=lambda d:-d['gap'])
 diff_a=sorted(({'term':t,'weight':float(w)} for t,w in ta['weights'].items() if t not in tb['weights']),key=lambda d:-d['weight'])[:DIFF_TERMS]
 diff_b=sorted(({'term':t,'weight':float(w)} for t,w in tb['weights'].items() if t not in ta['weights']),key=lambda d:-d['weight'])[:DIFF_TERMS]
 return {'top_terms_a':top_a,'top_terms_b':top_b,'shared_weight_gaps':shared_rows[:DIFF_TERMS],
         'only_in_a':diff_a,'only_in_b':diff_b}

def compare_runs(run_a,run_b,threshold):
 if not (isinstance(threshold,(int,float)) and np.isfinite(threshold) and 0.0<=float(threshold)<=0.95):
  raise ValueError('匹配门槛须为0..0.95之间的有限数')
 aligned=build_term_aligned(run_a,run_b)
 Va,Vb=aligned['Va'],aligned['Vb'];union=aligned['union_terms']
 cosine=_cosine_matrix(Va,Vb)
 # Hungarian 在完整余弦矩阵上求全局一对一最优（最小化负余弦和），
 # 再按门槛截断：低于门槛的配对不硬配，两个主题都保留为未匹配。
 row_ind,col_ind=linear_sum_assignment(-cosine)
 matched=[];matched_a=set();matched_b=set()
 for ra,rb in zip(row_ind.tolist(),col_ind.tolist()):
  sim=float(cosine[ra,rb])
  if sim>=float(threshold):
   ta=aligned['topics_a'][ra];tb=aligned['topics_b'][rb]
   matched.append({'topic_a_index':ra,'topic_b_index':rb,'label_a':ta['label'],'label_b':tb['label'],
                   'similarity':sim,'above_threshold':True,
                   'evidence':_term_evidence(ta,tb,union,Va[ra],Vb[rb])})
   matched_a.add(ra);matched_b.add(rb)
 unmatched_a=[{'topic_index':t['topic_index'],'label':t['label'],
               'top_terms':[{'term':w,'weight':float(x)} for w,x in sorted(t['weights'].items(),key=lambda kv:-kv[1])[:EVIDENCE_TERMS]]}
              for t in aligned['topics_a'] if t['topic_index'] not in matched_a]
 unmatched_b=[{'topic_index':t['topic_index'],'label':t['label'],
               'top_terms':[{'term':w,'weight':float(x)} for w,x in sorted(t['weights'].items(),key=lambda kv:-kv[1])[:EVIDENCE_TERMS]]}
              for t in aligned['topics_b'] if t['topic_index'] not in matched_b]
 # 被门槛拒绝的候选也保留下来，向编辑说明“本可配对但相似度不足”。
 rejected=[{'topic_a_index':int(ra),'topic_b_index':int(rb),'label_a':aligned['topics_a'][ra]['label'],
            'label_b':aligned['topics_b'][rb]['label'],'similarity':float(cosine[ra,rb]),'above_threshold':False}
           for ra,rb in zip(row_ind.tolist(),col_ind.tolist()) if float(cosine[ra,rb])<float(threshold)]
 matched.sort(key=lambda m:-m['similarity'])
 matched_sims=[m['similarity'] for m in matched]
 return {'rule_version':RULE_VERSION,'threshold':float(threshold),
         'k_a':len(aligned['topics_a']),'k_b':len(aligned['topics_b']),
         'union_terms':union,'shared_terms':aligned['shared_terms'],
         'vocabulary_only_a':aligned['only_a'],'vocabulary_only_b':aligned['only_b'],
         'cosine_matrix':cosine.tolist(),
         'hungarian_pairs':[{'topic_a_index':int(ra),'topic_b_index':int(rb),'similarity':float(cosine[ra,rb])} for ra,rb in zip(row_ind.tolist(),col_ind.tolist())],
         'matched':matched,'rejected_pairs':rejected,'unmatched_a':unmatched_a,'unmatched_b':unmatched_b,
         'matched_count':len(matched),'unmatched_count_a':len(unmatched_a),'unmatched_count_b':len(unmatched_b),
         'mean_matched_similarity':float(np.mean(matched_sims)) if matched_sims else None,
         'interpretation':'跨批次按实际词项并集对齐词权，L1重归一后计算余弦，Hungarian求全局一对一；低于门槛不硬配。相似度衡量词权分布重合，不是语义正确率；人工主题名仅作展示与核对。'}
