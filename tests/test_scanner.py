import unittest
import numpy as np
from scanner import clayton_copula, estimate_clayton_theta, scan_solidity_source, analyze_oracle_data, analyze_pool_data, analyze_transaction_data, build_report

class ScannerTests(unittest.TestCase):
    def test_clayton_boundaries(self):
        self.assertAlmostEqual(clayton_copula(1,1,2),1.0)
        self.assertGreater(clayton_copula(.05,.05,5),.0025)
    def test_theta_fit(self):
        rng=np.random.default_rng(7); x=rng.uniform(.001,.999,200); y=rng.uniform(.001,.999,200)
        theta,ll=estimate_clayton_theta(x,y); self.assertGreater(theta,0); self.assertTrue(np.isfinite(ll))
    def test_solidity_patterns(self):
        ids={x["id"] for x in scan_solidity_source("contract X { function x() public { require(tx.origin == msg.sender); } function y(address a) public { a.call(\"\"); } }")}
        self.assertIn("AUTH-001",ids); self.assertIn("CALL-001",ids)
    def test_oracle_deviation(self):
        rows=[{"source":"a","price":100,"timestamp":1000},{"source":"b","price":120,"timestamp":1000}]
        out=analyze_oracle_data(rows,now=1100,max_age_seconds=500,max_deviation=.03)
        self.assertTrue(any(x["id"]=="ORACLE-DEVIATION-001" for x in out))
    def test_pool_drop(self):
        rows=[{"pool":"p","timestamp":1,"reserve_usd":1000},{"pool":"p","timestamp":2,"reserve_usd":600}]
        self.assertTrue(analyze_pool_data(rows))
    def test_flashlike_signal(self):
        out=analyze_transaction_data([{"tx_hash":"x","borrow_events":1,"repay_events":1}])
        self.assertEqual(out[0]["id"],"TX-FLASHLIKE-001")
    def test_report_never_confirms_exploit(self):
        self.assertFalse(build_report(contract=[{"severity":"HIGH"}])["exploit_confirmed"])

if __name__=="__main__": unittest.main()
