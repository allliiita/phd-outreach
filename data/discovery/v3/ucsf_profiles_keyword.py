"""UCSF-wide Profiles keyword search -> data/roster/ucsf-keyword.jsonl. Run from repo root."""
import re,json,sys,html,unicodedata,requests,urllib.parse as up
sys.path.insert(0,'.');sys.path.insert(0,'data/discovery/v3')
from outreach.surnames import asian_tag
from ucsf_profiles_roster import rows2
UA="Mozilla/5.0 (academic-directory-research; contact via applicant email)"
INST="https://researcherprofiles.org/profile/171351"
KW=["machine learning","deep learning","artificial intelligence","neural network","computer vision","foundation model","large language model","computational neuroscience","medical imaging AI"]
def norm(s):
    s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower()
    s=re.sub(r"\b(md|phd|mph|ms|dr)\b","",s);return " ".join(re.sub(r"[^a-z ]"," ",s).split())
have={norm(json.loads(l)['name']) for l in open('data/tag/people.jsonl')}
def young(t):
    if re.search(r"adjunct|emerit|instructor|researcher|health sciences clinical|clinical professor|\bclin\b|lecturer|specialist|visiting|volunteer|recall",t,re.I):return False
    return bool(re.search(r"assistant prof|asst prof|associate prof|assoc prof",t,re.I))
def search(kw):
    u="https://profiles.ucsf.edu/search/default.aspx?searchtype=people&searchfor="+up.quote(kw)+"&exactphrase=false&institution="+INST+"&classuri=http://xmlns.com/foaf/0.1/Person&new=true"
    t=requests.get(u,headers={'User-Agent':UA},timeout=60).text
    n=int(re.search(r'Search Results \((\d+)\)',t).group(1))
    req=re.search(r'id="txtSearchRequest" name="txtSearchRequest" value="([^"]*)"',t).group(1)
    tp=-(-n//100);allr=[]
    for pg in range(1,tp+1):
        u2="https://profiles.ucsf.edu/search/default.aspx?searchtype=people&searchfor=%s&exactphrase=false&perpage=100&offset=0&page=%d&totalpages=%d&searchrequest=%s&sortby=&sortdirection=&showcolumns=11"%(up.quote(kw),pg,tp,up.quote(req,safe=''))
        allr+=rows2(requests.get(u2,headers={'User-Agent':UA},timeout=60).text)
    return u,n,allr
kept={};stats={}
for kw in KW:
    u,n,r=search(kw);ids={x[0] for x in r};stats[kw]=(n,len(ids))
    for pid,name,title,inst,dept,div,rt in r:
        name=html.unescape(name).strip();title=html.unescape(title).strip();dept=html.unescape(dept).strip()
        if pid in kept or not young(title) or asian_tag(re.sub(r",.*","",name))!="chinese":continue
        if re.search(r"biostat|epidemiolog|business|haas",dept+" "+div,re.I):continue
        if norm(re.sub(r",.*","",name)) in have or norm(name) in have:continue
        kept[pid]={"name":name,"institution":"University of California San Francisco","department":dept,"title_on_roster":title,"roster_url":u,"profile_url":pid,"quote":f"{name} | {title} | {dept} | {div} | {rt}","keyword":kw}
with open('data/roster/ucsf-keyword.jsonl','w') as f:
    for o in kept.values():f.write(json.dumps(o)+"\n")
print(stats);print(len(kept))
from collections import Counter;print(Counter(o['department'] for o in kept.values()))
