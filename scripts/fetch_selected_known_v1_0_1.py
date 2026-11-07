"""Second bounded acquisition batch, preserving all previous caches."""
import fetch_site_samples_v1_0_0 as probe
probe.OUT=probe.ROOT/'expansion/site-selected/known-v1.0.1'
probe.URLS=[('tang-'+pid,'https://www.guwendao.net/shiwenv_'+key+'.aspx') for pid,key in [
 ('155','44ba4afb80db'),('157','f6c40e3d4893'),('158','7cc200edc65e'),
 ('161','93ac46de573f'),('164','2716dfb4d439'),('166','796882166eaf'),
 ('168','1921957e6e83'),('169','eeb217f8cb2d')]]
if __name__=='__main__':probe.main()
