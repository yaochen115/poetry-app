"""Eight frequent missing characters, via the site's observed public word form."""
from urllib.parse import quote
import fetch_site_samples_v1_0_0 as probe
probe.OUT=probe.ROOT/'expansion/site-dictionary/priority-v1.0.0'
probe.URLS=[('char-'+str(ord(ch)),'https://www.guwendao.net/zici/search.aspx?value='+quote(ch))
            for ch in '堕窝熏冉严闷颍配']
if __name__=='__main__':probe.main()
