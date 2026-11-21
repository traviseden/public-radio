import {geometry,mapped} from '../../lib/snapshot.mjs';
export function getStaticPaths(){ return mapped().map(t=>({params:{id:t.id}})); }
export function GET({params}) {
  return new Response(geometry(params.id),{headers:{'Content-Type':'application/geo+json'}});
}
