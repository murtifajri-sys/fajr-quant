Saya inging membuat aplikasi untuk analisa saham, bernama Fajr Quant.
Aplikasi ini akan membantu saya untuk menganalisa saham, dengan menggunakan data dari Stockbit dan yahoofinance.
Untuk data dari Stockbit saya akan menggunakan API dari Stockbit, dan untuk data dari yahoofinance saya akan menggunakan API dari yahoofinance.
Data stockbit itu ada token yang harus saya gunakan, dan nanti bisa diinput secara manual, jd nanti dibuatkan form untuk input token stockbit.
Untuk data price yahoofinance digunakan untuk fallback jika data stockbit tidak tersedia.
Atau untuk intraday kita pakenya yang 30 menit, dan ambil dari yahoofinance.
Tapi untuk intraday kita buat ditahap selanjutkan, kita fikus ke daily dulu.
Untuk data dari stockbit bisa diambil dari ini  ananti km lihat data apa saja yang bisa digunakan data_sources.md. 
ini nanti km pisahkan ya analisis teknikal dan bandarmology. untuk fundamental kita skip dulu. 
Data teknikal nanti diambil minimal 500-100 hari terakhir. kemudian untuk bandarmology minimal 3 bulan terakhir.
Untuk teknikal kita fokus ke Struktur trend + Price Action, Volume + Breakout, Harmonic Pattern, Relative Strength, Candlestick Pattern, elliot wave. 
Jadi nanti km hitung indikator yang diperlukan, dan juga kamu simpan. 
untuk bandarmology harus sistem bisa deteksi hidden accumulation, silent accumulation, shakeout, absorption, bandar positioning, consistency. 
Juga foreign flow. perhatikan juga market regime. jd annti nya ada research engine, screener, chart dari masing-masing metode, paper trading, backtest.
kemudian dr semua itu nanti sy minta AI untuk kasih final recommendation. dan dikirimkan ke email, atau telegram, atau whatsapp. tp paling tahap awal fokus ke telegram dulu. 
dan sy ingin project terstruktur rapi dan lengkap dokumentasinya, dan selalu update dokumentasi kalo ada perubahan.
nanti km buat sistem scoring ya, cmn sy belum tau pasti scorignnya sperti apa nanti km buatin strateginya. 
jd nanti system bisa tau owh saham ini bisasane patuh atau cocok menggunakan indikator apa, apakah foreign flownya berperan, atau bandarmologynya lebih berperan, trs apakah termasuk fase awal, atau mengunggu konfirmais, atau sudah bisa entry, atau saatnya dijual, nanti bisa dikembangkan juga. 