import argparse
import io
import mysql.connector
import sys


htmlTemplate = """<!DOCTYPE HTML>
<html>
	<head>
		<title>{0} vs {1}</title>
		<meta http-equiv="content-type" content="text/html; charset=utf-8" />
		<link rel="stylesheet" href="codemirror/codemirror.css">
		<style type="text/css">			
			.CodeMirror {{
			  border: 1px solid #eee;
			  height: 100%;
			}}
		</style>
	</head>
	<body>	
		<script src="codemirror/codemirror.js"></script>
		<script src="codemirror/diff.js"></script>
		<script>
			var myCodeMirror = CodeMirror(document.body, {{
				value: "{2}",
				mode:  "diff",
				lineNumbers: true
			}});	
		</script>
	</body>
</html>"""


class DiffType:
	
	ADDED = 1
	REMOVED = 2
	UNCHANGED = 3

	def asPrefix(diffType):
		if diffType == DiffType.ADDED: 
			return "+"
		if diffType == DiffType.REMOVED: 
			return "-"
		return " "	

		
class Field:

	def __init__(self, name, sqlType):
		self.name = name
		self.sqlType =sqlType
		self.diffType = DiffType.UNCHANGED
		
	def __str__(self):
		return "field %s %s" % (self.name, self.sqlType)
		
	def __eq__(self, other):
		if type(self) == type(other):
			return self.name == other.name
		return False
		
		
class Table:

	def __init__(self, name):
		self.name = name
		self.fields = []
		self.diffType = DiffType.UNCHANGED

	def __str__(self):
		return "table %s" % self.name

	def __eq__(self, other):
		if type(self) == type(other):
			return self.name == other.name
		return False
		

def main(oldConf, newConf, outFile):	
	
	oldDB = mysql.connector.connect(**oldConf)
	newDB = mysql.connector.connect(**newConf)
	oldCursor = oldDB.cursor()							  				  
	newCursor = newDB.cursor() 
	
	oldTables = readTables(oldCursor)  
	newTables = readTables(newCursor)
	oldCursor.close()
	newCursor.close()			  
	oldDB.close()
	newDB.close()

	diff = calcDiff(oldTables, newTables)
	
	if outFile is None:
		text = get_diff_text(diff)
		print(text)
	else:
		if outFile.endswith('html'):
			text = get_diff_text(diff, True)
			html = htmlTemplate.format(oldConf["database"], newConf["database"], text)
			htmlFile = open(outFile, 'w')
			htmlFile.write(html)
			htmlFile.close()
		else:
			text = get_diff_text(diff)
			textFile = open(outFile, 'w')
			textFile.write(text)
			textFile.close()


def readTables(cursor):
	query = "SHOW TABLES"
	cursor.execute(query)
	tables = []
	for (row) in cursor:
		table = Table(row[0])
		tables.append(table)
	tables.sort(key = lambda table: table.name)
	readFields(tables, cursor)
	return tables

	
def readFields(tables, cursor):
	for table in tables:
		query = "SHOW COLUMNS IN " + table.name
		cursor.execute(query)
		for row in cursor:
			field = Field(row[0], row[1])
			table.fields.append(field)
		table.fields.sort(key = lambda field: field.name)


def calcDiff(oldTables, newTables):
	
	oldIdx = 0
	newIdx = 0
	diffTables = []
			
	while oldIdx < len(oldTables) or newIdx < len(newTables):
		
		if oldIdx >= len(oldTables):
			newTable = newTables[newIdx]
			tagTable(newTable, DiffType.ADDED)
			diffTables.append(newTable)
			newIdx += 1
			continue
			
		if newIdx >= len(newTables):
			oldTable = oldTables[oldIdx]
			tagTable(oldTable, DiffType.REMOVED)
			diffTables.append(oldTable)
			oldIdx += 1			
			continue
			
		oldTable = oldTables[oldIdx]
		newTable = newTables[newIdx]
		
		if oldTable.name == newTable.name:
			diffTable = calcDiffTable(oldTable, newTable)
			diffTables.append(diffTable)
			newIdx += 1
			oldIdx += 1
			continue
			
		if oldTable in newTables:
			newTable = newTables[newIdx]
			tagTable(newTable, DiffType.ADDED)
			diffTables.append(newTable)
			newIdx += 1
		else:
			oldTable = oldTables[oldIdx]
			tagTable(oldTable, DiffType.REMOVED)
			diffTables.append(oldTable)
			oldIdx += 1
	
	return diffTables


def calcDiffTable(oldTable, newTable):
	
	oldFields = oldTable.fields
	newFields = newTable.fields

	oldIdx = 0
	newIdx = 0
	diffTable = Table(oldTable.name)
	diffFields = diffTable.fields
	
	while oldIdx < len(oldFields) or newIdx < len(newFields):
		
		if oldIdx >= len(oldFields):
			newField = newFields[newIdx]
			newField.diffType = DiffType.ADDED
			diffFields.append(newField)
			newIdx += 1
			continue
			
		if newIdx >= len(newFields):
			oldField = oldFields[oldIdx]
			oldField.diffType = DiffType.REMOVED			
			diffFields.append(oldField)
			oldIdx += 1			
			continue
			
		oldField = oldFields[oldIdx]
		newField = newFields[newIdx]
		
		if oldField.name == newField.name:
			if oldField.sqlType == newField.sqlType:
				diffFields.append(newField)
			else:
				# type changed
				oldField.diffType = DiffType.REMOVED
				newField.diffType = DiffType.ADDED
				diffFields.append(oldField)
				diffFields.append(newField)
			newIdx += 1
			oldIdx += 1
			continue
			
		if oldField in newFields:
			newField = newFields[newIdx]
			newField.diffType = DiffType.ADDED
			diffFields.append(newField)
			newIdx += 1
		else:
			oldField = oldFields[oldIdx]
			oldField.diffType = DiffType.REMOVED			
			diffFields.append(oldField)
			oldIdx += 1		
	
	return diffTable
	
	
def tagTable(table, diffType):
	table.diffType = diffType
	for field in table.fields:
		field.diffType = diffType

	
def get_diff_text(diff, compact = False):
	writer = io.StringIO()
	lineBreak = "\\n" if compact else "\n"
	for table in diff:
		tableHead = "%s %s (" %  (DiffType.asPrefix(table.diffType), table.name)
		writer.write(tableHead)
		writer.write(lineBreak)
		for field in table.fields:
			fieldText = "%s    %s [%s]" % (DiffType.asPrefix(field.diffType), 
											field.name, field.sqlType)
			writer.write(fieldText)
			writer.write(lineBreak)		
		tableFooter = "%s )" % DiffType.asPrefix(table.diffType)
		writer.write(tableFooter) 
		writer.write(lineBreak)
		writer.write(lineBreak)
	diffText = writer.getvalue()
	writer.close()
	return diffText	


def read_config(confString, arg, parser):
	"""
	Reads the database connection arguments from the configuration string. 
	The string should have the format 
		host:port/database?user=user&password=password
	See also http://dev.mysql.com/doc/connector-python/en/
	connector-python-connectargs.html.
	"""
	if confString is None:
		print("ERROR: %s is not defined" % arg)
		parser.print_help()
		sys.exit(0)
	 
	config = {}
	hostStr = None
	pathStr = None
	queryStr = None
	if '/' in confString:
		s = confString.split('/') 
		hostStr = s[0]
		pathStr = s[1]
	else:
		pathStr = confString
	
	if '?' in pathStr:
		s = pathStr.split('?')
		pathStr = s[0]
		queryStr = s[1]
	
	config["database"] = pathStr
	
	if hostStr is not None:
		if ':' in hostStr:
			s = hostStr.split(':')
			config["host"] = s[0]
			config["port"] = s[1]
		else:
			config["host"] = hostStr
	
	if queryStr is None:
		config["user"] = "root"
		config["password"] = ""
	else:
		s = queryStr.split('&')
		for pair in s:
			if '=' in pair:
				(key, sep, value) = pair.partition('=')
				config[key] = value
	
	if not "user" in config.keys():
		config["user"] = "root"
	
	if not "password" in config.keys():
		config["password"] = ""
	
	return config
		
if __name__ == '__main__':

	parser = argparse.ArgumentParser(
		description='mysqldiff: calculate the diff between two MySQL databases')
	parser.add_argument('-old', dest='oldDb', help='the connection to the old database')
	parser.add_argument('-new', dest='newDb', help='the connection to the new database')
	parser.add_argument('-out', dest='outFile', 
		help='the path to the output file where the diff should be stored (html or text)')
	args = parser.parse_args()
	
	oldConf = read_config(args.oldDb, 'OLDDB', parser)
	newConf = read_config(args.newDb, 'NEWDB', parser)
		
	main(oldConf, newConf, args.outFile)
	
	

  
  
  

