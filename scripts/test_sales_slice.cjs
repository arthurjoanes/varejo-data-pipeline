/* Domain checks for the offline store/day explorer; does not start Spark. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync('src/retail_pipeline/report_sales.js', 'utf8'), context);
const { sliceSales, salesMoney, recentSalesPeriod } = vm.runInContext('({sliceSales, salesMoney, recentSalesPeriod})', context);
const rows = [
  { business_date:'2026-01-01', store_id:'S01', net_revenue_brl:'90071992547409.93', sales_count:2, units:3, item_lines:2 },
  { business_date:'2026-01-08', store_id:'S01', net_revenue_brl:'0.07', sales_count:1, units:1, item_lines:1 },
  { business_date:'2026-01-08', store_id:'S02', net_revenue_brl:'20.00', sales_count:1, units:2, item_lines:1 },
];
assert.equal(sliceSales(rows,'','','').revenue, 9007199254743000n);
assert.equal(salesMoney(9007199254740993n), 'R$ 90.071.992.547.409,93');
assert.equal(sliceSales(rows,'2026-01-08','2026-01-08','S01').revenue, 7n);
assert.equal(sliceSales(rows,'2026-01-08','2026-01-08','S02').sales, 1n);
assert.equal(sliceSales(rows,'2026-02-01','','').revenue, null);
assert.equal(sliceSales([{...rows[0],net_revenue_brl:null}],'','','').revenue, null);
assert.equal(sliceSales([{...rows[0],net_revenue_brl:'0.00'}],'','','').revenue, 0n);
assert.throws(()=>sliceSales(rows,'2026-01-08','2026-01-01',''), /inicial/);
assert.equal(recentSalesPeriod(rows,7).from,'2026-01-02');
assert.equal(recentSalesPeriod(rows,7).to,'2026-01-08');
assert.equal(rows[0].net_revenue_brl,'90071992547409.93');
console.log('11 offline sales-slice checks passed');
