const katex = require('katex');
const fs = require('fs');
const outPath = process.argv[2];

const F = {
  pop:      [String.raw`N = H_0 + C_0,\qquad \rho = C_0/N`, false],
  time:     [String.raw`t = 0,1,\ldots,T`, false],
  match:    [String.raw`|\mathcal{P}_{i,t}| \le a,\qquad (i,j)\in\mathcal{A}_t \Rightarrow j\notin\mathcal{B}_{i,t},\ i\notin\mathcal{B}_{j,t}`, true],
  sync:     [String.raw`\text{type}_{i,s}=\text{type}_{i,t}\quad \text{for every transaction } s \text{ settled in step } t`, true],
  conv:     [String.raw`m_{i,t}\ge p \ \Longrightarrow\ \text{type}_{i,t+1}=C \quad (\text{irreversible})`, true],
  exit:     [String.raw`w_{i,t}\le 0 \Rightarrow w_{i,t}=0,\ \text{exit};\qquad r_{i,t}\ge q \Rightarrow \text{exit with } w_{i,t}\ \text{retained}`, true],
  sij:      [String.raw`S_{ij}=g_{ij}^{i}+g_{ij}^{j}`, false],
  srules:   [String.raw`S^{HH}=2g_{HH}>0,\qquad S^{CC}=2g_{CC}<0,\qquad S^{HC}=g_{HC}^{H}+g_{HC}^{C}=0`, true],
  wt:       [String.raw`W_T=\sum_{t=1}^{T}\ \sum_{(i,j)\in\mathcal{A}_t}\left(g_{ij}^{i}+g_{ij}^{j}\right)`, true],
  wtr:      [String.raw`W_T^{R}=W_T-\sum_{t=1}^{T}\sum_{i\in\mathcal{I}_t} c`, true],
  mech:     [String.raw`Y_i^{k}=\alpha_k+\beta_k E_i+\gamma_k^{\prime}X_i+\delta_k(E_i\times\rho_i)+\lambda_k^{\prime}\left(E_i\times 1[p_i]\right)+\varepsilon_i^{k},\qquad k\in\{F,C,K\}`, true],
  collapse1:[String.raw`Y_i=\alpha+\beta E_i+\gamma^{\prime}X_i+\varepsilon_i`, true],
  collapse2:[String.raw`Y_i=\alpha+\beta^{\prime}E_i+\phi_1 F_i+\phi_2 C_i+\phi_3 K_i+\gamma^{\prime}X_i+u_i`, true],
  share:    [String.raw`1-\hat{\beta}^{\prime}/\hat{\beta}`, false],
  acct:     [String.raw`\sum_{i=1}^{N} w_{i,T}=N w_0+W_T^{\mathrm{real}}-C_T^{\mathrm{real}}`, true],
  y:        [String.raw`Y=\min(T^{\mathrm{collapse}},T)`, false],
  sijreal:  [String.raw`S_{ij}^{\mathrm{real}}=\Delta w_i+\Delta w_j`, false],
};

const out = {};
for (const [k, v] of Object.entries(F)) {
  out[k] = katex.renderToString(v[0], {
    displayMode: v[1], throwOnError: false, strict: false, output: 'html'
  });
}
fs.writeFileSync(outPath, JSON.stringify(out), 'utf8');
console.log('rendered', Object.keys(out).length, 'formulas');
