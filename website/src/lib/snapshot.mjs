// Build-time only. Nothing in this module is imported by client scripts.
import { DatabaseSync } from 'node:sqlite';
import { resolve } from 'node:path';
import sql from 'sql-template-tag';

const db = new DatabaseSync(resolve('../data/web.sqlite'), { readOnly: true });
const all = q => db.prepare(q.sql).all(...q.values);
const one = q => db.prepare(q.sql).get(...q.values);
export const number = value => value == null ? 'Unavailable' : Math.round(value).toLocaleString('en-US');
// Ratios of allocated counts from the same table, never means of area percentages.
export function shares(metrics) {
  const byId=new Map(metrics.map(m=>[m.id,m]));
  const result=new Map();
  for(const [numerators, denominators] of [
    [['children','working_age','seniors'],['children','working_age','seniors']],
    [['hispanic',...Array.from({length:7},(_,i)=>`race_${i+3}`)],['hispanic',...Array.from({length:7},(_,i)=>`race_${i+3}`)]],
    [['degree'],['adults25']], [['poverty'],['poverty_base']],
    [['income_0','income_1','income_2','income_3'],['income_0','income_1','income_2','income_3']],
    [['owned','rented'],['households']],
  ]) {
    const base=denominators.map(k=>byId.get(k));
    if(!base.every(m=>m && !m.missing_groups)) continue;
    const denominator=base.reduce((n,m)=>n+m.estimate,0);
    for(const key of numerators) {
      const m=byId.get(key);
      if(denominator>0 && m && !m.missing_groups) result.set(key,(100*m.estimate/denominator).toFixed(1)+'%');
    }
  }
  return result;
}
export const built = one(sql`SELECT value FROM build WHERE key='built'`).value;
export const stations = () => all(sql`SELECT t.id,t.name,t.residents,s.state,s.city,s.affiliation,
  s.licensee,s.lat,s.lon,s.reason,o.name owner_name
  FROM target t JOIN station s ON s.id=t.id LEFT JOIN target o ON o.id=s.owner
  WHERE t.kind='station' ORDER BY t.name COLLATE NOCASE,t.id`);
export const owners = () => all(sql`SELECT t.id,t.name,t.residents,count(s.id) members
  FROM target t JOIN station s ON s.owner=t.id WHERE t.kind='owner'
  GROUP BY t.id ORDER BY t.name COLLATE NOCASE`);
export const targets = () => all(sql`SELECT id,kind FROM target ORDER BY kind,id`);
export const mapped = () => all(sql`SELECT id FROM target WHERE geometry IS NOT NULL`);
export const geometry = id => {
  const r=one(sql`SELECT t.geometry,b.west,b.south,b.east,b.north FROM target t
    JOIN footprint_key k ON k.target_id=t.id JOIN footprint_bounds b ON b.spatial_id=k.spatial_id
    WHERE t.id=${id}`);
  return JSON.stringify({type:'Feature', id, properties:{}, bbox:[r.west,r.south,r.east,r.north], geometry:JSON.parse(r.geometry)});
};
export const sources = () => Object.fromEntries(all(sql`SELECT key,value FROM build`).map(r=>[r.key,
  r.key==='source_manifest' ? JSON.parse(r.value) : r.value]));
export function detail(id) {
  const item = one(sql`SELECT id,kind,name,residents,unassigned_residents,geometry IS NOT NULL mapped FROM target WHERE id=${id}`);
  const station = one(sql`SELECT s.*,o.name owner_name FROM station s LEFT JOIN target o ON o.id=s.owner WHERE s.id=${id}`);
  const metrics = all(sql`SELECT m.*,p.estimate,p.moe90,p.missing_groups FROM profile p
    JOIN metric m ON m.id=p.metric_id WHERE p.target_id=${id} ORDER BY m.ordinal`);
  const members = item.kind === 'owner' ? all(sql`SELECT t.id,t.name,t.residents,s.state,s.reason,s.evidence
    FROM station s JOIN target t ON s.id=t.id WHERE s.owner=${id} ORDER BY t.name COLLATE NOCASE`) : [];
  return {item,station,metrics,members};
}
