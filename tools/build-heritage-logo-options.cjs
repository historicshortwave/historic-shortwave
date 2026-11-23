const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');

const out = path.join(__dirname, '../design/branding/heritage-logo-options');
fs.mkdirSync(out, {recursive: true});

// Original geometric slab-serif outlines; no external fonts or image resources.
const letters = {
  H: 'M0 0H28V8H20V23H50V8H42V0H70V8H62V46H70V54H42V46H50V31H20V46H28V54H0V46H8V8H0Z',
  E: 'M0 0H70V17H61V8H20V23H47V17H55V38H47V31H20V46H61V37H70V54H0V46H8V8H0Z',
  R: 'M0 0H54L66 10V23L54 32H42L58 46H70V54H40V46H45L31 32H20V46H29V54H0V46H8V8H0Z M20 8V24H49L54 20V12L49 8Z',
  I: 'M4 0H66V8H42V46H66V54H4V46H28V8H4Z',
  T: 'M0 0H70V18H61V8H42V46H54V54H16V46H28V8H9V18H0Z',
  A: 'M24 0H46L65 46H70V54H43V46H52L47 34H23L18 46H27V54H0V46H5Z M27 26H43L35 8Z',
  G: 'M14 0H58L68 10V18H56V12L52 8H20L12 16V38L20 46H50L56 40V34H36V26H70V34H66V44L56 54H14L0 40V14Z',
};
function wordmark() {
  return `<g transform="translate(263 63)" fill="#fff" fill-rule="evenodd">${[...'HERITAGE'].map((c,i) => `<path transform="translate(${i*78} 0)" d="${letters[c]}"/>`).join('')}</g>`;
}
const ink = '#101010';
const beacon = `<g fill="none" stroke="${ink}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M111 134L134 59L157 134M120 106H148M125 90H143M114 127H154M125 90L148 106L114 127M143 90L120 106L154 127"/>
  <path d="M114 50Q103 62 114 74M154 50Q165 62 154 74M101 39Q79 62 101 86M167 39Q189 62 167 86"/>
  <path d="M100 137H168"/><circle cx="134" cy="59" r="4" fill="${ink}" stroke="none"/>
</g>`;
const world = `<g fill="none" stroke="${ink}" stroke-width="4">
  <circle cx="132" cy="90" r="49"/><ellipse cx="132" cy="90" rx="22" ry="49"/>
  <path d="M83 90H181M91 65Q132 78 173 65M91 115Q132 102 173 115M132 41V139"/>
  <path d="M69 125L194 55" stroke-width="7"/>
  <path d="M186 51L198 52L193 64" stroke-width="4" stroke-linejoin="round"/>
</g>`;
const flash = `<path d="M142 39L99 94H127L113 140L169 80H140L154 39Z" fill="${ink}"/>
<g fill="none" stroke="${ink}" stroke-width="4" stroke-linecap="square"><path d="M69 72H85M66 89H82M69 106H85M180 72H196M184 89H200M180 106H196"/></g>`;
const options = [
  {
    slug: 'heritage-broadcast-beacon', name: 'Broadcast Beacon',
    note: 'A radio mast and radiating arcs in a streamlined instrument badge.',
    shape: `<path d="M80 18H910L946 54V126L910 162H80L14 125V55Z" fill="${ink}"/>
      <path d="M81 26H907L938 57V123L907 154H81L22 120V60Z" fill="none" stroke="#fff" stroke-width="3"/>
      <circle cx="134" cy="90" r="65" fill="#fff"/>${beacon}`,
  },
  {
    slug: 'heritage-world-dial', name: 'World Dial',
    note: 'A globe and directional signal for the international shortwave theme.',
    shape: `<rect x="14" y="18" width="932" height="144" rx="35" fill="${ink}"/>
      <rect x="23" y="27" width="914" height="126" rx="27" fill="none" stroke="#fff" stroke-width="3"/>
      <path d="M49 34H211V146H49Q30 146 30 127V53Q30 34 49 34Z" fill="#fff"/>${world}`,
  },
  {
    slug: 'heritage-signal-flash', name: 'Signal Flash',
    note: 'A lightning flash in a diamond, framed by an angular equipment plate.',
    shape: `<path d="M32 18H928V34H946V146H928V162H32V146H14V34H32Z" fill="${ink}"/>
      <path d="M40 26H920V42H938V138H920V154H40V138H22V42H40Z" fill="none" stroke="#fff" stroke-width="3"/>
      <path d="M134 29L223 90L134 151L45 90Z" fill="#fff"/>${flash}`,
  },
];
function svg(contents, width=960, height=180, title='Heritage logo concept') {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img"><title>${title}</title>${contents}</svg>`;
}
async function render(name, markup, width) {
  if (/<(?:image|use|foreignObject)\b|(?:href|url\()/i.test(markup)) throw new Error('External resources are prohibited');
  fs.writeFileSync(path.join(out, `${name}.svg`), markup);
  await sharp(Buffer.from(markup), {limitInputPixels: 20_000_000}).resize({width}).png().toFile(path.join(out, `${name}.png`));
}
(async () => {
  for (const o of options) await render(o.slug, svg(o.shape+wordmark(),960,180,`Heritage: ${o.name}`),1920);
  const rows = options.map((o,i) => {
    const y=145+i*310;
    return `<g transform="translate(100 ${y})">${o.shape}${wordmark()}</g>
      <text x="114" y="${y-19}" font-family="DejaVu Sans,sans-serif" font-size="21" font-weight="700" fill="${ink}">${i+1} / ${o.name.toUpperCase()}</text>
      <text x="114" y="${y+210}" font-family="DejaVu Sans,sans-serif" font-size="17" fill="#555">${o.note}</text>`;
  }).join('');
  await render('heritage-logo-options-comparison', svg(`<rect width="1160" height="1100" fill="#fff"/>
    <text x="114" y="55" font-family="DejaVu Sans,sans-serif" font-size="30" font-weight="700" fill="${ink}">HERITAGE / Three logo directions</text>
    <text x="114" y="87" font-family="DejaVu Sans,sans-serif" font-size="17" fill="#555">Original monochrome badge studies for the HR-64 receiver.</text>
    ${rows}<text x="114" y="1050" font-family="DejaVu Sans,sans-serif" font-size="15" fill="#777">Concepts only. The receiver preview has not been changed.</text>`,1160,1100,'Heritage: three logo directions'),2320);
  console.log('Created three transparent logo PNGs, editable SVGs, and a comparison sheet in '+out);
})().catch(e => {console.error(e);process.exitCode=1});
