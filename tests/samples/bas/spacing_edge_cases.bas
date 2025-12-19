10 REM Test spacing edge cases for detokenizer
20 REM Number followed by keyword
30 FOR I=1 TO 10 STEP 2
40 IF X=5 THEN GOTO 100
50 IF Y=10 AND Z=20 THEN PRINT "OK"
60 IF A=1 OR B=2 THEN STOP
70 X=5 MOD 3
80 REM Keyword followed by number
90 GOTO 100
100 GOSUB 200
110 ON 1 GOTO 120,130
120 RETURN
130 REM Keyword followed by keyword
140 IF NOT X THEN END
150 PRINT USING "###";X
160 FOR J=1 TO 10
170 NEXT J
180 REM Multiple statements per line
190 A=1:B=2:C=3
200 PRINT "A";:PRINT "B"
210 REM Functions with parentheses
220 A=ABS(SIN(COS(1)))
230 B$=LEFT$(RIGHT$(MID$("TEST",1,3),2),1)
240 C=INT(RND(1)*10)
250 REM TAB and SPC (special tokens ending with paren)
260 PRINT TAB(10);SPC(5);"TEXT"
270 REM String concatenation and comparison
280 A$="HELLO"+"WORLD"
290 IF A$="TEST" THEN PRINT "YES"
300 IF A$<>"TEST" THEN PRINT "NO"
310 REM Hex and octal constants
320 A=&HFF
330 B=&O77
340 C=&H1234
350 REM REMARK (REM + ARK combined token)
360 REMARK This is a remark
370 REM Operators without spaces in source
380 A=1+2-3*4/5^2\3
390 B=(A+B)*(C-D)
400 REM Line continuation after colon
410 A=1:B=2:PRINT A;B
999 END
