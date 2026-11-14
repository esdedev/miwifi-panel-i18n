# Translation brief: Xiaomi router web UI (zh-CN → en)

Source: stock web admin panel of a Xiaomi BE3600 2.5G router (firmware 1.0.87). Strings come
from LuCI templates (`kind: template`) and a Vue.js single-page app (`kind: js`). The output
goes into `translations/en.json`. Translate **from the Chinese yourself**: do not copy or adapt
any existing translation (other projects' translation files, `.po` files such as xmir-patcher's).
Use a plain, concise UI style.

## Output

Write a JSON object `{ "<id>": "<english>" , ... }` with **every id** of your chunk, UTF-8,
no comments, to the output path given in your task. Nothing else in the file.

## Hard rules (the output is substituted mechanically)

1. Keep every placeholder and markup **exactly**: `%s`, `%d`, `%1`, `{0}`, `{name}`, `${...}`,
   `<br>`, `<a ...>`, `</span>`, `&nbsp;`, entities, and **backslash sequences as written**
   (`\n`, `\t`, ` `, `\"`). Do not add new backslashes or new HTML.
2. Keep leading/trailing whitespace and leading `\n` + indentation exactly as in the source.
3. Keep numbering/bullets (`1.`, `2、` → `2.`, `4.4`) and the `*` prefix of required-field hints.
4. Chinese punctuation → ASCII: `，`→`, ` `。`→`. ` `：`→`: ` `（）`→`()` `《X》`→`"X"` `、`→`, `.
   Do not end short labels/buttons with a period.
5. Do not translate brand/product names: Xiaomi, Redmi, Mi Home, MiWiFi, Mesh, Wi-Fi, IPTV,
   PPPoE, DHCP, DNS, VPN, UPnP, QoS, MAC, SSID, WPS, 2.4G, 5G, 5G-Game.
6. Keep it short (buttons/labels are narrow). Sentence case for sentences, Title Case only
   for short menu/section titles.
7. Legal/privacy text (user agreement, privacy policy, experience program): do not translate
   it for this repository; return the source unchanged. Full translations of those documents
   are derivative works and stay out of the repository (see LEGAL.md).
8. If a string is a fragment (e.g. `或者`, `个设备`), translate the fragment so it still reads
   naturally when concatenated (`or`, ` devices`).
9. Untranslatable/garbage (e.g. code that slipped in) → return the source unchanged.

## Glossary

| zh | en |
|---|---|
| 路由器 | router |
| 小米路由器 | Xiaomi router |
| 管理后台 | admin panel |
| 上网设置 | Internet settings |
| 宽带账号 / 宽带账户 | PPPoE username (broadband account) — use "Broadband account" in labels |
| 宽带密码 | Broadband password |
| 拨号 / PPPoE拨号 | PPPoE dial-up |
| 光猫 | optical modem (ONT) — in short labels "modem" |
| 上级设备 / 上级路由 | upstream device / upstream router |
| 中继 / 无线中继 / 有线中继 | repeater / wireless repeater / wired repeater |
| 有线 / 无线 | wired / wireless |
| 访客Wi-Fi | Guest Wi-Fi |
| 双频合一 | Combine 2.4G and 5G |
| 终端 / 设备 | device |
| 网口 / LAN口 / WAN口 | port / LAN port / WAN port |
| 自动获取IP | Automatic IP (DHCP) |
| 静态IP | Static IP |
| 恢复出厂设置 | Factory reset |
| 升级 / 固件 | upgrade / firmware |
| 小米账号 | Xiaomi account |
| 绑定 / 解绑 | bind / unbind |
| 用户体验改善计划 / 用户体验改进计划 | User Experience Improvement Program |
| 隐私政策 | Privacy Policy |
| 用户许可使用协议 | User License Agreement |
| 信号强度 | signal strength |
| 网速 / 测速 | speed / speed test |
| 黑名单 / 白名单 | blocklist / allowlist |
| 家长控制 | Parental control |
| 端口转发 | Port forwarding |
| 子网掩码 / 网关 | Subnet mask / Gateway |
| 正在… | …ing (e.g. 正在检测 → Checking...) |
| 确定 / 取消 / 保存 / 应用 | OK / Cancel / Save / Apply |
| 下一步 / 上一步 | Next / Back |
