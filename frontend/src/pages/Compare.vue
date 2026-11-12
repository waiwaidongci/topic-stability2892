<script setup lang="ts">
import {ref,computed} from 'vue';
import type {Run,User,Comparison,MatchedPair} from '../types/domain';
import {researchApi} from '../api/research';
import {useAsync} from '../hooks/useAsync';
import PageTitle from '../components/common/PageTitle.vue';
import Notice from '../components/common/Notice.vue';
import Empty from '../components/common/Empty.vue';
import Table from '../components/common/Table.vue';
import {dec,pct,date} from '../utils/format';
import {DEFAULT_THRESHOLD} from '../constants/comparison';

const props=defineProps<{runs:Run[];comparisons:Comparison[];user:User;reload:()=>Promise<any>}>();
const succeeded=computed(()=>props.runs.filter(r=>r.status==='succeeded'));
const runA=ref(0),runB=ref(0),name=ref('两批展签主题延续核对'),threshold=ref(DEFAULT_THRESHOLD);
const focusId=ref(0);
const {task,act}=useAsync();

const focus=computed(()=>props.comparisons.find(c=>c.id===focusId.value)||props.comparisons[0]);
const selectedA=ref<number|null>(null);
// 按 A 侧主题索引从最新数据派生，轮询刷新后选中的匹配仍保持实时。
const focusPair=computed<MatchedPair|null>(()=>{
 if(!focus.value)return null;
 if(selectedA.value==null)return focus.value.result.matched[0]||null;
 return focus.value.result.matched.find(m=>m.topic_a_index===selectedA.value)||focus.value.result.matched[0]||null;
});
function openComparison(c:Comparison){focusId.value=c.id;selectedA.value=c.result.matched[0]?.topic_a_index??null}
function selectPair(m:MatchedPair){selectedA.value=m.topic_a_index}

async function submit(){
 await act(async()=>{
  if(!runA.value||!runB.value)throw new Error('请选择两个不同的成功任务');
  if(runA.value===runB.value)throw new Error('请选择两个不同的任务');
  const c=await researchApi.compare({run_a_id:runA.value,run_b_id:runB.value,name:name.value,threshold:Number(threshold.value)});
  await props.reload();openComparison(c);
 },'对比已按当前规则与门槛计算，旧结论已重算');
}
async function refresh(c:Comparison){
 await act(async()=>{const fresh=await researchApi.refreshComparison(c.id);await props.reload();openComparison(fresh);},'已按最新规则版本重新计算');
}
const runName=(id:number)=>props.runs.find(r=>r.id===id)?.name||('#'+id);
</script>

<template>
 <PageTitle index="07 / BATCH COMPARISON" title="两批主题，按实际词项再相遇。" description="词表、主题数与编号都可能不同；按词项并集对齐词权后做全局一对一匹配，低于门槛不硬配。相似度是词权分布重合，不是语义正确率，主题名保留人工命名。"/>
 <Notice :error="task.error" :message="task.message"/>

 <form class="editor compare-form" @submit.prevent="submit">
  <h2>选择两个成功任务并设定匹配门槛</h2>
  <div class="form-grid">
   <label>第一批任务（A）
    <select v-model.number="runA" required>
     <option :value="0" disabled>请选择成功任务</option>
     <option v-for="r in succeeded" :key="r.id" :value="r.id">VOL {{String(r.id).padStart(3,'0')}} · {{r.name}} / K={{r.config.k}} / {{r.result.vocabulary?.length||0}}词</option>
    </select>
   </label>
   <label>第二批任务（B）
    <select v-model.number="runB" required>
     <option :value="0" disabled>请选择成功任务</option>
     <option v-for="r in succeeded" :key="r.id" :value="r.id">VOL {{String(r.id).padStart(3,'0')}} · {{r.name}} / K={{r.config.k}} / {{r.result.vocabulary?.length||0}}词</option>
    </select>
   </label>
   <label>对比名称<input v-model="name" required maxlength="100"/></label>
   <label>匹配门槛（余弦低于此值不硬配）
    <div class="threshold-row"><input type="range" min="0" max="0.95" step="0.01" v-model.number="threshold"/><b class="mono">{{dec(threshold,2)}}</b></div>
   </label>
  </div>
  <p class="fine">同一对任务重复提交会覆盖旧结论并按当前门槛重算；对比规则版本升级后，历史结果会标记“口径已失效”，需手动刷新重算。仅成功（succeeded）任务可对比。</p>
  <button class="primary" :disabled="task.busy||user.role==='viewer'||succeeded.length<2">{{task.busy?'计算中…':'计算跨批次匹配 →'}}</button>
  <p v-if="user.role==='viewer'">观察员可查看对比，创建需研究编辑权限。</p>
 </form>

 <Empty v-if="!comparisons.length" title="还没有跨批次对比" help="选择两批各自成功的主题任务，调整门槛后计算；低相似度主题会保留为未匹配。"/>

 <template v-else>
  <div class="section-title"><h2>对比记录</h2><small>规则版本与门槛随结论保存</small></div>
  <Table :headers="['对比 / 名称','任务 A → 任务 B','门槛','匹配 / 未匹配(A·B)','口径状态','建立时间','']">
   <tr v-for="c in comparisons" :key="c.id" :class="{'row-stale':c.stale}">
    <td><small>COMPARE / {{String(c.id).padStart(2,'0')}}</small><strong>{{c.name}}</strong></td>
    <td><small>{{runName(c.run_a_id)}}</small><strong>→ {{runName(c.run_b_id)}}</strong></td>
    <td class="mono">{{dec(c.threshold,2)}}</td>
    <td>{{c.result.matched_count}} 对 <small>未匹配 {{c.result.unmatched_count_a}} · {{c.result.unmatched_count_b}}</small></td>
    <td><span v-if="c.stale" class="badge failed">口径已失效</span><span v-else class="badge succeeded">{{c.result.rule_version}}</span></td>
    <td class="mono">{{date(c.updated_at||c.created_at)}}</td>
    <td><button class="text-button" @click="openComparison(c)">阅读匹配依据 ↗</button></td>
   </tr>
  </Table>

  <template v-if="focus">
   <div class="section-title">
    <h2>{{focus.name}} <small class="rule-tag">RULE {{focus.result.rule_version}}</small></h2>
    <button v-if="focus.stale&&user.role!=='viewer'" class="primary" :disabled="task.busy" @click="refresh(focus)">按新规则重算 →</button>
   </div>
   <Notice v-if="focus.stale" error="该结论基于旧版对比规则，数值与匹配不再代表当前口径，请重算后再用于编辑判断。"/>

   <section class="compare-summary">
    <div><small>任务 A / K={{focus.result.k_a}}</small><b>{{focus.run_a?.name}}</b><small class="mono">{{(focus.run_a?.fingerprint||'').slice(0,18)}}…</small></div>
    <div><small>任务 B / K={{focus.result.k_b}}</small><b>{{focus.run_b?.name}}</b><small class="mono">{{(focus.run_b?.fingerprint||'').slice(0,18)}}…</small></div>
    <div><small>门槛 / 平均匹配余弦</small><b>{{dec(focus.threshold,2)}}<span> / {{dec(focus.result.mean_matched_similarity??undefined)}}</span></b><small>{{focus.result.matched_count}} 对一对一匹配</small></div>
    <div><small>词表对齐</small><b>{{focus.result.union_terms.length}}<span> 并集词</span></b><small>共享 {{focus.result.shared_terms.length}} · A独有 {{focus.result.vocabulary_only_a.length}} · B独有 {{focus.result.vocabulary_only_b.length}}</small></div>
   </section>

   <div class="section-title"><h2>全局一对一匹配（{{focus.result.matched.length}}）</h2><small>Hungarian 最小化负余弦和后再按门槛截断</small></div>
   <Empty v-if="!focus.result.matched.length" title="门槛下没有成立的匹配" help="降低门槛可重新计算；当前两批主题词权分布重合不足，全部保留为未匹配。"/>
   <div v-else class="match-tabs">
    <button v-for="m in focus.result.matched" :key="m.topic_a_index+'-'+m.topic_b_index" :class="{active:focusPair&&focusPair.topic_a_index===m.topic_a_index}" @click="selectPair(m)">
     <span>A{{m.topic_a_index+1}} ↔ B{{m.topic_b_index+1}}</span><b :style="{opacity:.45+m.similarity*.55}">{{dec(m.similarity)}}</b>
    </button>
   </div>

   <article v-if="focusPair" class="evidence-card">
    <header>
     <div><small>A 主题 {{focusPair.topic_a_index+1}} / 人工命名</small><h3>{{focusPair.label_a}}</h3></div>
     <span class="similarity big">{{dec(focusPair.similarity)}}</span>
     <div><small>B 主题 {{focusPair.topic_b_index+1}} / 人工命名</small><h3>{{focusPair.label_b}}</h3></div>
    </header>
    <div class="evidence-grid">
     <section>
      <small>A 侧高词权词（L1 归一后）</small>
      <div v-for="t in focusPair.evidence.top_terms_a" :key="'a'+t.term" class="term-line"><span>{{t.term}}</span><i :style="{width:(t.weight/(focusPair.evidence.top_terms_a[0]?.weight||1)*100)+'%'}"></i><b>{{pct(t.weight)}}</b></div>
     </section>
     <section>
      <small>B 侧高词权词（L1 归一后）</small>
      <div v-for="t in focusPair.evidence.top_terms_b" :key="'b'+t.term" class="term-line"><span>{{t.term}}</span><i :style="{width:(t.weight/(focusPair.evidence.top_terms_b[0]?.weight||1)*100)+'%'}"></i><b>{{pct(t.weight)}}</b></div>
     </section>
    </div>
    <div class="evidence-grid">
     <section>
      <small>共享词词权差（|wA−wB|，前 {{focusPair.evidence.shared_weight_gaps.length}}）</small>
      <Table :headers="['词','A词权','B词权','差']">
       <tr v-for="g in focusPair.evidence.shared_weight_gaps" :key="g.term"><td><strong>{{g.term}}</strong></td><td>{{pct(g.weight_a)}}</td><td>{{pct(g.weight_b)}}</td><td class="mono">{{dec(g.gap)}}</td></tr>
      </Table>
     </section>
     <section class="diff-box">
      <small>差异词：只在一侧词权中出现</small>
      <p><b>仅 A：</b><template v-if="focusPair.evidence.only_in_a.length">{{focusPair.evidence.only_in_a.map(d=>d.term+'('+pct(d.weight)+')').join('、')}}</template><span v-else>无</span></p>
      <p><b>仅 B：</b><template v-if="focusPair.evidence.only_in_b.length">{{focusPair.evidence.only_in_b.map(d=>d.term+'('+pct(d.weight)+')').join('、')}}</template><span v-else>无</span></p>
     </section>
    </div>
   </article>

   <div class="section-title"><h2>双方未匹配主题</h2><small>低相似度不硬配：这些主题在另一批没有成立对应</small></div>
   <div class="unmatched-grid">
    <section>
     <small>A 侧未匹配（{{focus.result.unmatched_a.length}}）</small>
     <article v-for="u in focus.result.unmatched_a" :key="'ua'+u.topic_index" class="unmatched-item">
      <strong>A{{u.topic_index+1}} · {{u.label}}</strong>
      <p>{{u.top_terms.map(t=>t.term).join('、')||'无有效词权'}}</p>
     </article>
     <p v-if="!focus.result.unmatched_a.length" class="fine">全部 A 主题均已匹配。</p>
    </section>
    <section>
     <small>B 侧未匹配（{{focus.result.unmatched_b.length}}）</small>
     <article v-for="u in focus.result.unmatched_b" :key="'ub'+u.topic_index" class="unmatched-item">
      <strong>B{{u.topic_index+1}} · {{u.label}}</strong>
      <p>{{u.top_terms.map(t=>t.term).join('、')||'无有效词权'}}</p>
     </article>
     <p v-if="!focus.result.unmatched_b.length" class="fine">全部 B 主题均已匹配。</p>
    </section>
   </div>

   <div v-if="focus.result.rejected_pairs.length" class="section-title"><h2>被门槛拒绝的 Hungarian 候选</h2><small>算法给过一对一候选，但余弦低于门槛 {{dec(focus.threshold,2)}}，故不成立</small></div>
   <Table v-if="focus.result.rejected_pairs.length" :headers="['候选 A','候选 B','余弦','门槛']">
    <tr v-for="r in focus.result.rejected_pairs" :key="r.topic_a_index+'-'+r.topic_b_index">
     <td><small>A{{r.topic_a_index+1}}</small><strong>{{r.label_a}}</strong></td>
     <td><small>B{{r.topic_b_index+1}}</small><strong>{{r.label_b}}</strong></td>
     <td class="mono">{{dec(r.similarity)}}</td><td class="mono">{{dec(focus.threshold,2)}}</td>
    </tr>
   </Table>

   <p class="excluded-note">{{focus.result.interpretation}} 任务 A 独有词：{{focus.result.vocabulary_only_a.join('、')||'无'}}；任务 B 独有词：{{focus.result.vocabulary_only_b.join('、')||'无'}}。</p>
  </template>
 </template>
</template>
