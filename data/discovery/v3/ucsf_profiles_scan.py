import re,requests,json,sys,urllib.parse as up
UA="Mozilla/5.0 (academic-directory-research; contact via applicant email)"
INST="https://researcherprofiles.org/profile/171351"
D=json.load(open('data/discovery/v3/ucsf_profiles_depts.json'))
def rows(t):
    out=[]
    for m in re.finditer(r"font-weight:bold'>([^<]*)</div>\s*<br/><br/><u>Title</u> <br/>([^<]*?)\s*<br/><br/><u>Institution</u><br/>([^<]*?)\s*<br/><br/><u>Department</u><br/>([^<]*?)\s*<br/><br/><u>Division</u><br/>([^<]*?)\s*<br/><br/><u>Researcher Type</u><br/>([^\"]*?)\"",t):
        out.append(dict(name=m.group(1),title=m.group(2),inst=m.group(3),dept=m.group(4),div=m.group(5),rtype=m.group(6)))
    return out
def scan(dept,perpage=100):
    u="https://profiles.ucsf.edu/search/default.aspx?searchtype=people&institution="+INST+"&department="+D[dept]+"&classuri=http://xmlns.com/foaf/0.1/Person&new=true"
    t=requests.get(u,headers={'User-Agent':UA},timeout=60).text
    n=int(re.search(r'Search Results \((\d+)\)',t).group(1))
    req=re.search(r'id="txtSearchRequest" name="txtSearchRequest" value="([^"]*)"',t).group(1)
    res=rows(t)
    if len(res)<n:  # first page holds only 15 rows: page through ALL pages (perpage=100, page=1..ceil(n/100))
        tp=-(-n//perpage);res=[]
        for pg in range(1,tp+1):
            u2="https://profiles.ucsf.edu/search/default.aspx?searchtype=people&searchfor=&exactphrase=false&perpage=%d&offset=0&page=%d&totalpages=%d&searchrequest=%s&sortby=&sortdirection=&showcolumns=11"%(perpage,pg,tp,up.quote(req,safe=''))
            res+=rows(requests.get(u2,headers={'User-Agent':UA},timeout=60).text)
    return n,res
if __name__=="__main__":
    for d in sys.argv[1:]:
        n,r=scan(d);print(d,n,len(r))
        from collections import Counter
        print(Counter(x['title'] for x in r).most_common(12))
