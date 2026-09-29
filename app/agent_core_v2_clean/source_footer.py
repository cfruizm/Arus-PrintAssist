from __future__ import annotations
from collections import OrderedDict

def _page(value):
 value=str(value or "").strip()
 return int(value) if value.isdigit() else value

def _list(values):
 values=list(values)
 if not values:return "página no especificada"
 numeric=sorted({x for x in values if isinstance(x,int)});other=sorted({str(x) for x in values if x not in (None,"") and not isinstance(x,int)})
 parts=[str(x) for x in numeric]+other
 if len(parts)==1:return "pág. "+parts[0]
 if len(parts)==2:return "págs. "+parts[0]+" y "+parts[1]
 return "págs. "+", ".join(parts[:-1])+" y "+parts[-1]

def compact_sources(evidence,cited_ids):
 by_id={str(x.get("id")):x for x in evidence or []};docs=OrderedDict()
 for rid in cited_ids or []:
  item=by_id.get(str(rid))
  if not item:continue
  identity=str(item.get("url") or item.get("source") or item.get("title") or rid)
  row=docs.setdefault(identity,{"title":str(item.get("title") or "Fuente sin título"),"pages":[]})
  raw=item.get("page") or (item.get("metadata") or {}).get("page_label")
  page=_page(raw)
  if page not in (None,"") and page not in row["pages"]:row["pages"].append(page)
 rows=[f"{x['title']}, {_list(x['pages'])}." for x in docs.values()]
 if not rows:return ""
 if len(rows)==1:return "**Fuente documental:** "+rows[0]
 return "**Fuentes documentales**\n"+"\n".join("- "+x for x in rows)
