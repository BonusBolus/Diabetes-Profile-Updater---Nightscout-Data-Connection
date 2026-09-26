"""Optional Node checks cover browser lifecycle without contacting Nightscout."""
from pathlib import Path
import shutil
import json
import subprocess
import tempfile
import unittest
import pandas as pd
from datetime import timedelta
import plotly.graph_objects as go
from test_nightscout import sample_data
from graph_view import navigation_bundle, viewer_html
from nightscout_charts import graph_figures

class ViewerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for viewer JavaScript checks')
    def test_overlay_navigation_and_hidden_tab_lifecycle(self):
        loaded=sample_data()
        start=loaded['loaded_at']-timedelta(days=2)
        loaded['data']['target']=pd.DataFrame([dict(time=start+timedelta(hours=5),end=start+timedelta(hours=5,minutes=30),
            low=144,high=144,profile_low=118.8,profile_high=118.8,source='Temporary target',reason='Activity')])
        profile=go.Figure(go.Scatter(x=[0,1440],y=[9,10],name='LenStandardV17',line_color='#ff9800',meta=dict(kind='profile',label='LenStandardV17',unit='g/U',source_role='ref2')))
        profile.update_layout(meta=dict(profile_changes=[600]),title='I:C',yaxis=dict(title='g/U',rangemode='normal'))
        view=dict(loaded=loaded,days=[loaded['first'],loaded['last']],mode='Median + band',
                  layers=['Glucose','Temporary basal','IOB + boluses','COB + carbs','Variable sensitivity','Custom graph'],overlay='None')
        from nightscout_charts import add_profile_guides
        add_profile_guides(profile,[600],True)
        loaded['last']=loaded['last']+timedelta(days=1)
        loaded['loaded_at']=loaded['loaded_at']+timedelta(days=1)
        view['days']=[loaded['first'],loaded['first']+timedelta(days=1),loaded['last']]
        profiles={'ic':profile}
        for key,label,unit,value in [('isf','ISF','mmol/L/U',4),('basal','Basal','U/h',1),('target','Target','mmol/L',6.6)]:
            fig=go.Figure(profile);fig.data[0].y=[value,value];fig.data[0].meta['unit']=unit
            fig.update_layout(title=label,yaxis_title=unit,meta=dict(profile_changes=[800]))
            from nightscout_charts import add_profile_guides
            fig.layout.shapes=[]
            add_profile_guides(fig,[800],True)
            profiles[key]=fig
        # Include variable sensitivity for the retained panel and profile overlay.
        loaded['data']['variable_sens']=pd.DataFrame([dict(time=start,value=90,label='variable_sens')])
        html=viewer_html(graph_figures(profile,**view,unit='mmol/L',dark=True),True,navigation_bundle(profile,view,'mmol/L',True,profiles,'ic'))
        source=html.split('<script>')[-1].split('</script>')[0]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'viewer.js';path.write_text(source)
            result=subprocess.run(['node',str(Path(__file__).with_name('viewer_checks.cjs')),str(path),str(Path(folder)/'custom-rendered.json')],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            for rendered in json.loads((Path(folder)/'custom-rendered.json').read_text()):
                go.Figure(rendered)  # Validate every generated custom trace/axis with Plotly's schema.
