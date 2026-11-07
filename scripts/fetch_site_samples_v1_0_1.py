"""Follow two observed public dictionary links; retain the v1.0.0 probe."""
from fetch_site_samples_v1_0_0 import main,ROOT
import fetch_site_samples_v1_0_0 as probe

probe.OUT=ROOT/'expansion/site-samples/v1.0.1'
probe.URLS=[('dictionary-panxi','https://www.guwendao.net/zici/search.aspx?value=%E7%A3%BB%E6%BA%AA'),
            ('dictionary-qichi','https://www.guwendao.net/zici/search.aspx?value=%E6%A0%96%E8%BF%9F')]

if __name__=='__main__':main()
