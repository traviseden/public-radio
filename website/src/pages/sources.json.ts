import {sources} from '../lib/snapshot.mjs';
export function GET(){return Response.json(sources());}
