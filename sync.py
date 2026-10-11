#!/usr/bin/env python3
"""PITLANE UK event feed aggregator. Only ingest feeds you are authorised to use."""
import json, os, re, hashlib, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'sources.json').read_text())

def unfold(s):
    return re.sub(r'\r?\n[ \t]', '', s)

def unescape(s):
    return s.replace('\\n',' ').replace('\\,',',').replace('\\;',';').replace('\\\\','\\')

def date(s):
    s=s.strip()
    if re.match(r'^\d{8}',s): return f'{s[:4]}-{s[4:6]}-{s[6:8]}'
    return ''

def read_ics(url):
    req=urllib.request.Request(url,headers={'User-Agent':'PITLANE-UK/1.0 (event calendar sync)'})
    with urllib.request.urlopen(req,timeout=25) as resp:
        raw=resp.read(5_000_000).decode('utf-8-sig','replace')
    if 'BEGIN:VCALENDAR' not in raw: raise ValueError('Not an iCalendar feed')
    for block in unfold(raw).split('BEGIN:VEVENT')[1:]:
        content=block.split('END:VEVENT',1)[0]
        fields={}
        for line in content.splitlines():
            if ':' in line:
                k,v=line.split(':',1)
                fields[k.split(';')[0].upper()]=unescape(v.strip())
        yield fields

def clean(s): return re.sub(r'[^a-z0-9]+',' ',s.lower()).strip()

def category(text):
    t=text.lower()
    rules=[('Bike racing',['motorcycle','superbike','motocross','bike race','bike racing']),('Drifting',['drift']),('Drag racing',['drag racing','drag strip']),('Rallying',['rally','hillclimb','hill climb','sprint']),('Modified show',['modified','tuner','stance','jdm','custom car']),('Classic cars',['classic','vintage','historic show']),('Car meet',['car meet','cars and coffee','car show']),('Circuit racing',['race','racing','circuit','touring','gt championship'])]
    return next((cat for cat,words in rules if any(w in t for w in words)),'Other motorsport')

def sync():
    checked=datetime.now(timezone.utc).isoformat(timespec='seconds')
    out=[]; errors=[]; seen={}
    for src in CONFIG['sources']:
        if not src.get('enabled',False): continue
        try:
            if src['type']!='ics': raise ValueError('Unsupported source type')
            for v in read_ics(src['url']):
                name=v.get('SUMMARY','').strip(); start=date(v.get('DTSTART',''))
                if not name or not start or start < '2026-01-01': continue
                venue=v.get('LOCATION','').strip()
                link=v.get('URL','').strip() or src.get('website','')
                key='|'.join((clean(name),start,clean(venue)))
                record={'id':hashlib.sha256(key.encode()).hexdigest()[:16],'name':name,'date':start,'end_date':date(v.get('DTEND','')),'venue':venue,'region':'','category':category(name+' '+v.get('DESCRIPTION','')),'organiser':src['name'],'status':'Unverified','official_url':link,'ticket_url':'','source_names':[src['name']],'source_urls':[src['url']],'last_checked':checked,'description':v.get('DESCRIPTION','')[:400]}
                if key in seen:
                    existing=seen[key];existing['source_names'].append(src['name']);existing['source_urls'].append(src['url'])
                    if not existing['official_url'] and link:existing['official_url']=link
                else:seen[key]=record;out.append(record)
        except Exception as e: errors.append({'source':src['name'],'error':str(e)[:200]})
    # Add approved, manually reviewed records; feed records cannot override them.
    manual=ROOT/'data/manual-events.json'
    if manual.exists():
        for v in json.loads(manual.read_text()):
            if not all(v.get(k) for k in ('name','date','venue','official_url')) or v['date'] < '2026-01-01':continue
            key='|'.join((clean(v['name']),v['date'],clean(v['venue'])))
            if key in seen: continue
            v.setdefault('id',hashlib.sha256(key.encode()).hexdigest()[:16]);v.setdefault('last_checked',checked);v.setdefault('status','Unverified');v.setdefault('source_names',['Manual review']);out.append(v);seen[key]=v
    # If feeds temporarily fail, retain previously published entries rather than wiping the calendar.
    target=ROOT/'data/events.json'
    if errors and target.exists():
        old=json.loads(target.read_text()).get('events',[])
        ids={x['id'] for x in out}
        for v in old:
            if v.get('id') not in ids and v.get('date','') >= '2026-01-01':
                v['status']='Stale — recheck source';out.append(v)
    out.sort(key=lambda x:(x.get('date',''),x['name']))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'generated_at':checked,'event_count':len(out),'source_errors':errors,'events':out},ensure_ascii=False,indent=2)+'\n')
    print(f'Published {len(out)} events; {len(errors)} source errors')
    for e in errors:print('ERROR',e['source'],e['error'])

if __name__=='__main__':sync()
