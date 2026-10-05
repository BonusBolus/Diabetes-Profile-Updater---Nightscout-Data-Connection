"""Rendered event hover alignment, scrolling readouts and compact overlays."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
import plotly.graph_objects as go
import test_health22
from graph_view import prepared_graphs, viewer_html

class Health23Tests(unittest.TestCase):
    setUp=test_health22.Health22Tests.setUp
    load=test_health22.Health22Tests.load
    enriched=test_health22.Health22Tests.enriched

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_rendered_hover_markers_readout_scroll_and_overlay_select(self):
        loaded=self.enriched()
        profile=go.Figure(go.Scatter(x=[0,1440],y=[10,10],meta=dict(kind='profile'),name='Standard v17'))
        profile.update_layout(title='I:C',xaxis=dict(range=[0,1440]),yaxis=dict(title='g/U'))
        paths=[]
        for mode in ('One day','Multiple days','Median + band'):
            view=dict(loaded=loaded,days=[self.last] if mode=='One day' else [self.first,self.last],mode=mode,
                      layers=['Garmin · Steps','Garmin · Activity','Custom graph'])
            figures,nav=prepared_graphs(profile,view,'mmol/L',True)
            html=viewer_html(figures,True,nav)
            self.assertIn('<select id="overlay-select"',html)
            self.assertIn('prefers-reduced-motion',html)
            path=self.folder/f'{len(paths)}.js';path.write_text(html.split('<script>')[-1].split('</script>')[0],encoding='utf-8');paths.append(str(path))
        target=self.folder/'plots.json'
        result=subprocess.run(['node',str(Path(__file__).with_name('health23_viewer_checks.cjs')),*paths,str(target)],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        for figure in json.loads(target.read_text()):go.Figure(figure)

if __name__=='__main__':unittest.main()
