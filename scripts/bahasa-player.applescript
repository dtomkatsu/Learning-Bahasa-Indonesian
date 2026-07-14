set htmlPath to "/Users/dtomkatsu/Learning-Bahasa-Indonesian/index.html"
set fileURL to "file://" & htmlPath
try
	do shell script "open -na 'Google Chrome' --args --app=" & quoted form of fileURL
on error
	do shell script "open " & quoted form of htmlPath
end try
