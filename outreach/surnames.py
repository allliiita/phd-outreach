"""Loose surname -> heritage tag, used only to ORDER outreach (applicant preference), never to verify anything.
Deliberately generous: ambiguous names (Lee, Long, Park, Young...) count as matches.

  asian_tag("Weijing Tang") -> "chinese";  asian_tag("Aditi Raghunathan") -> "south_asian";  else None
"""
from __future__ import annotations

import re
import unicodedata

CHINESE = set("""
an ai bai ban bao bei bi bian bo cai cao cen chai chang chao chen cheng chi chiu chou chu chuang chui chun chung
cong cui dai dan deng di diao ding dong dou du duan fan fang fei feng fu gan gao ge geng gong gou gu guan guo
han hang hao he heng hong hou hsieh hsu hu hua huang hui huo ji jia jian jiang jiao jin jing ju kang ke kong kou
kuang kuo kwan kwok lai lam lan lang lau lei leng leung li lian liang liao lim lin ling liu long lou lu luan luo lv
lyu ma mai mao mei meng mi miao min ming mo mu ng ni nie ning niu ou pan pang pei peng ping pu qi qian qiao qin
qing qiu qu quan ran rao ren rong ruan sang shan shang shao she shen sheng shi shu shuai si song su sui sun tai
tan tang tao teng tian tong tsai tsang tseng tso tu wan wang wei wen weng wong wu xi xia xian xiang xiao xie xin
xing xiong xu xue yan yang yao ye yi yin ying yip yong you yu yuan yue yun zang zeng zha zhai zhan zhang zhao
zhen zheng zhong zhou zhu zhuang zhuo zong zou chan cheung chow fung ho hung kwong lo loh mak ngai poon siu tam
tsui wai woo yau yee yeung yim yiu chiang chien chin chuang hsiao hsiung kao kuan lee liou tsao tsou wey
""".split())
EAST_ASIAN = set("""
kim park choi jung jeong kang cho yoon yun jang lim han oh seo shin kwon hwang ahn song hong jeon ko moon yang
son bae baek heo nam noh ryu yoo yu
sato suzuki takahashi tanaka watanabe ito yamamoto nakamura kobayashi kato yoshida yamada sasaki yamaguchi
matsumoto inoue kimura hayashi shimizu yamazaki mori abe ikeda hashimoto ishikawa ogawa okada hasegawa murakami
kondo fujita goto nishimura saito fujii okamoto matsuda nakajima harada ono tamura takeuchi kaneko wada nakano
ishii ueda morita hara shibata sakai kudo yokoyama miyazaki miyamoto uchida takagi ando taniguchi ohno maruyama
imai takada fujiwara murata takeda sugiyama noguchi kubo arai chiba iwasaki sakamoto
nguyen tran le pham hoang huynh phan vu vo dang bui do ngo duong ly trinh dinh
""".split())
SOUTH_ASIAN = set("""
patel shah singh kumar sharma gupta agarwal agrawal jain mehta reddy rao iyer iyengar krishnan raghunathan
ramanan subramanian srinivasan venkatesan narayanan chandra chatterjee banerjee mukherjee bose das dutta ghosh
sen roy chowdhury bhattacharya mishra pandey tiwari verma saxena joshi kulkarni deshpande desai nair menon pillai
kapoor malhotra arora bhatia sethi goel garg bansal mittal khan ahmed hussain ali chaudhary choudhury yadav
ganguly saha sinha basu ray mohan raman ravi anand prasad murthy naidu bhat hegde shetty kamath pai
""".split())


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def asian_tag(name: str) -> str | None:
    parts = [p for p in re.sub(r"[^a-z\- ]", " ", _ascii(re.sub(r"\s+\d{4}$", "", name))).split() if len(p) > 1]
    if not parts:
        return None
    last = parts[-1]
    if last in CHINESE:
        return "chinese"
    if last in EAST_ASIAN:
        return "east_asian"
    if last in SOUTH_ASIAN:
        return "south_asian"
    if any(p in CHINESE for p in last.split("-")):
        return "chinese"
    return None


PRIORITY = {"chinese": 0, "east_asian": 1, "south_asian": 2, None: 3}
