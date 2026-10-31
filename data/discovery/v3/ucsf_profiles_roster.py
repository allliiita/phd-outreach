"""Build data/roster/ucsf-<slug>.jsonl from UCSF Profiles dept searches (all pages). Run from repo root."""
import re,json,sys,html
sys.path.insert(0,'data/discovery/v3')
import ucsf_profiles_scan as s
INSTN="University of California San Francisco"
FAC=re.compile(r"professor|lecturer|instructor|researcher|scientist|faculty",re.I)
UNITS={ # profiles dept -> (slug, unit label, group)
 "Bioengineering":("ucsf-bts","Bioengineering and Therapeutic Sciences (Profiles dept Bioengineering)","G2"),
 "Radiology":("ucsf-radiology","Radiology and Biomedical Imaging","G3"),
 "Pharmaceutical Chemistry":("ucsf-pharmchem","Pharmaceutical Chemistry","G3"),
 "Biochemistry and Biophysics":("ucsf-biochem","Biochemistry and Biophysics","G3"),
 "Computational Precision Heal":("ucsf-cph","Computational Precision Health","G2"),
 "Computational Health Scienc":("ucsf-chs","Computational Health Sciences (Bakar CHSI)","G2"),
 "Cell and Tissue Biology":("ucsf-ctb","Cell and Tissue Biology","G3"),
 "Neurology":("ucsf-neurology","Neurology","G4"),
 "Psychiatry":("ucsf-psychiatry","Psychiatry","G4"),
 "Neurological Surgery":("ucsf-neurosurgery","Neurological Surgery","G4"),
}
def rows2(t):
    out=[]
    pat=re.compile(r"<input type=\"hidden\" id=\"(https://researcherprofiles.org/profile/\d+)\" value=\"<div style='font-size:13px;font-weight:bold'>([^<]*)</div>\s*<br/><br/><u>Title</u> <br/>([^<]*?)\s*<br/><br/><u>Institution</u><br/>([^<]*?)\s*<br/><br/><u>Department</u><br/>([^<]*?)\s*<br/><br/><u>Division</u><br/>([^<]*?)\s*<br/><br/><u>Researcher Type</u><br/>([^\"]*?)\"")
    for m in pat.finditer(t): out.append(m.groups())
    return out
s_rows=s.rows
def main(depts):
    import requests,urllib.parse as up
    for d in depts:
        slug,unit,grp=UNITS[d]
        # reuse scan's paging but capture raw pages
        pages=[]
        orig=requests.get
        def cap(*a,**k):
            r=orig(*a,**k);pages.append(r.text);return r
        s.requests.get=cap
        try: n,res=s.scan(d)
        finally: s.requests.get=orig
        allrows=[]
        for t in pages: allrows+=rows2(t)
        if len(allrows)>len(res): allrows=allrows[-len(res):] if len(pages)==1 else allrows
        seen=set();out=[];dropped=0
        for pid,name,title,inst,dept,div,rt in allrows:
            if pid in seen: continue
            seen.add(pid)
            name=html.unescape(name).strip();title=html.unescape(title).strip()
            if not (FAC.search(title) or FAC.search(rt)) or re.search(r"specialist|resident physician|clinical fellow|postdoc",title,re.I):
                dropped+=1;continue
            out.append({"name":name,"institution":INSTN,"department":unit,"title_on_roster":title,
              "roster_url":"https://profiles.ucsf.edu/search/advanced (Department=%s)"%d,"profile_url":pid,
              "quote":f"{name} | {title} | {dept} | {div} | {rt}","filter":"all","via":"ucsf-profiles"})
        out=[o for o in out]
        with open(f"data/roster/{slug}.jsonl","w") as f:
            for o in out: f.write(json.dumps(o)+"\n")
        print(d,"page_count",n,"parsed",len(res),"raw_unique",len(seen),"kept",len(out),"dropped",dropped,flush=True)
if __name__=="__main__": main(sys.argv[1:] or list(UNITS))
