// Reviewed research mappings only. Never edits the master workbook or app catalog.
const fs=require('fs'),path=require('path'),base=path.resolve(__dirname,'../research/qsl');
const all=JSON.parse(fs.readFileSync(path.join(base,'candidate-matches.json')));
const exact=[2,3,4,6,9,10,14,16,19,20,21,22,29,31,35,36,38,39,40,41,42,43,45,46,49,50,51,53,54,56,57,59,60,64,65,66,68,69,71,72,75,77,78,79,80,81,82,83,85,86,87,88,90,95,101,102,106,107,110,114,116,117,118,119,120,121,122,123,125,126,128,130,133,139,141,142,143,144,145,146,152,154,155,156,157,158,160,162,164,166,168,170,175,176,177,178,179,182,184,187,190,191,192,193,194,195,196,199,201,202,204,205,210,213,214,219,220,221,222,223,224,227,231,232,235,236,239,243,247,248,249,252,254,256,261,263,264,265,273,274,275,276,277,278,279,280,286];
const overrides={
 7:'maranhao.html',8:'maranhao.html',11:'swazi.htm',13:'rinca.htm',17:'kellyequ2.htm',23:'gabon.htm',
 27:'mali.htm',28:'mali.htm',30:'tanzan.htm',34:'turks.htm',47:'india4.htm',52:'gabon1.htm',61:'riga4.htm',
 89:'mauritania.html',93:'kellycol2.htm',96:'guatemala73.htm',97:'guatemala73.htm',98:'kelly302.htm',
 100:'camnat.html',111:'mozam3.html',138:'bare.html',147:'chad.htm',148:'chad.htm',149:'chad.htm',
 153:'h23.html',159:'rtawa.html',203:'nambia.htm',206:'bolivia21.htm',225:'baha.html',
 234:'nepal.htm',238:'mada.htm',244:'niger.html',245:'soloman.htm',246:'soloman.htm',
 267:'portguinea.htm',268:'bissau.htm',269:'bissau.htm',272:'culture.htm',283:'yemen.htm',
 25:'https://radiotapes.com/QSL_Europe',
 48:'https://radiotapes.com/qsl_asia',
 55:'https://radiotapes.com/qsl_south_america',58:'https://radiotapes.com/qsl_south_america',
 91:'https://radiotapes.com/qsl_africa',92:'https://radiotapes.com/qsl_africa',94:'https://radiotapes.com/qsl_africa',
 115:'https://radiotapes.com/qsl_africa',218:'https://radiotapes.com/qsl_africa',
 229:'https://radiotapes.com/qsl_oceana',230:'https://radiotapes.com/qsl_north_central_america',250:'https://radiotapes.com/qsl_north_central_america'
};
const related={
 24:['djiboutimain.html','Djibouti verifications indexed; exact RTVD era/name needs checking.'],
 70:['brazilmain.htm','Several Radio Educadora stations; master label lacks locality. Do not choose by name alone.'],
 99:['surinamemain.htm','SRS/STICHTING Radio Omroep Suriname service candidate; abbreviation/local service match needs checking.'],
 103:['yemennorth.htm',"Radio Sana'a QSLs found, but master label says South Yemen. Identity/geography conflict; do not award automatically."],
 105:['mozammain.htm','Several Radio Clube callsigns; exact historical outlet/era must be checked.'],
 113:['https://radiotapes.com/qsl_africa','Azores Emissora Nacional gallery candidate; regional outlet attribution needs review.'],
 127:['h20.html','Emissora Voz do Zaire candidate; provincial Bassacongo identity not established.'],
 129:['nacionaangola.htm','National Angola verification is available; Bassacongo outlet-specific attribution not established.'],
 163:['ghana.html','GBC service gallery; specific channel card not established.'],
 167:['ghana.html','GBC service gallery; Radio One channel attribution not established.'],
 173:['eqguineamain.htm','Bata/Equatorial Guinea verifications indexed; Rio Muni historical identity not established.'],
 174:['eqguineamain.htm','Bata/Equatorial Guinea verifications indexed; Rio Muni historical identity not established.'],
 183:['nacionaangola.htm','Carrier service card only; no UNITA program QSL established.'],
 185:['kellyequ2.htm','CRE Radiodifusora del Ecuador candidate; confirm against master record identity.'],
 186:['ivory.html','Radio Abidjan service cards; RTVI naming/era match needs checking.'],
 188:['moscowkyrg.html','Radio Moscow via Frunze is not proof of a domestic Radio Frunze QSL.'],
 189:['kellypac1.htm','WSZO cards are listed for 1987; historical branding/recording-era match needs checking.'],
 209:['venmain.htm','Composite recording: Radio Rumbos and Ecos del Torbes each have verifications; choose only after segment identification.'],
 211:['angola.htm','Colonial Radio Clube de Cabinda candidate; later Emisora Regional attribution not established.'],
 216:['h50.html','Radio Moscow via Dushanbe is not proof of a domestic Radio Dushanbe QSL.'],
 241:['brazilmain.htm','Radio Cultura galleries do not establish the Cuiaba outlet.'],
 251:['fredp17.htm','Radio Continente candidate; Reloj Continente historical identity needs review.'],
 253:['kelly6.htm','Radio Los Andes candidate; Huamachuco attribution must be checked.'],
 255:['angola.htm','Colonial Radio Clube de Cabinda candidate; later Emisora Regional attribution not established.'],
 257:['https://radiotapes.com/qsl_africa','Radio Centrafrique national-service gallery; exact branding/era needs checking.'],
 258:['https://radiotapes.com/qsl_africa','Radio Centrafrique national-service gallery; exact branding/era needs checking.'],
 259:['https://radiotapes.com/qsl_africa','Radio Centrafrique national-service gallery; exact branding/era needs checking.'],
 260:['https://radiotapes.com/qsl_africa','Radio Centrafrique national-service gallery; exact branding/era needs checking.'],
 284:['1er3.htm','Radio Clube do Huambo candidate; later Emissora Regional identity not established.'],
 285:['saudimain.html','Saudi Arabia Broadcasting Service card indexed (1987); BSKSA service/era attribution needs checking.']
};
const full=p=>p.startsWith('http')?p:'http://www.swlqslmuseum.com/'+p;
 for(const x of all){
 x.status='Unresolved';x.match_url='';x.match_note='';
 if(exact.includes(x.i)){x.status='Located';x.match_url=x.candidates[0].url;x.match_note=x.candidates[0].title;}
 if(overrides[x.i]){x.status='Located';x.match_url=full(overrides[x.i]);x.match_note='Reviewed station-name/abbreviation mapping; inspect source for era and artwork type.';}
 if(related[x.i]){x.status='Related';x.match_url=full(related[x.i][0]);x.match_note=related[x.i][1];}
 if([109,226].includes(x.i)){x.status='Identity hold';x.match_note='Unidentified or mixed station label; requires recording/segment identity resolution before a QSL can be assigned.';}
 if(x.i===103)x.status='Identity hold';
}
fs.writeFileSync(path.join(base,'reviewed-matches.json'),JSON.stringify(all,null,2));
console.log('Counts',all.reduce((o,x)=>(o[x.status]=(o[x.status]||0)+1,o),{}));
for(const x of all.filter(x=>x.status==='Unresolved'))console.log(x.i,x.station);
