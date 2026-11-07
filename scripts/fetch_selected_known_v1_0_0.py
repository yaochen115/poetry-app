"""Read publicly indexed article URLs; no site-login/search bypass."""
import fetch_site_samples_v1_0_0 as probe
probe.OUT=probe.ROOT/'expansion/site-selected/known-v1.0.0'
probe.URLS=[
 ('tang-156','https://www.guwendao.net/shiwenv_c348339f28fd.aspx'),
 ('tang-160','https://www.guwendao.net/shiwenv_b7820a12ebaa.aspx'),
 ('tang-162','https://www.guwendao.net/shiwenv_b0d3f72465ef.aspx'),
 ('tang-165','https://www.guwendao.net/shiwenv_d50eb19399e6.aspx')]
if __name__=='__main__':probe.main()
