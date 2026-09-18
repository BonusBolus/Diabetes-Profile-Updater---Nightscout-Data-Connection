"""Optional Node checks cover browser lifecycle without contacting Nightscout."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import plotly.graph_objects as go
from test_nightscout import sample_data
from graph_view import navigation_bundle, viewer_html
from nightscout_charts import graph_figures

class ViewerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for viewer JavaScript checks')
    def test_overlay_navigation_and_hidden_tab_lifecycle(self):
        loaded=sample_data()
        profile=go.Figure(go.Scatter(x=[0,1440],y=[9,10],name='LenStandardV17',meta=dict(kind='profile',label='LenStandardV17',unit='g/U')))
        profile.update_layout(title='I:C',yaxis=dict(title='g/U',rangemode='normal'))
        view=dict(loaded=loaded,days=[loaded['first'],loaded['last']],mode='Median + band',
                  layers=['Glucose','Temporary basal','IOB','Boluses','COB','Carbs'],overlay='None')
        html=viewer_html(graph_figures(profile,**view,unit='mmol/L',dark=True),True,navigation_bundle(profile,view,'mmol/L',True))
        source=html.split('<script>')[-1].split('</script>')[0]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'viewer.js';path.write_text(source)
            result=subprocess.run(['node',str(Path(__file__).with_name('viewer_checks.cjs')),str(path)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
