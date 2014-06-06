mysqldiff
---------
A small Python script that creates a diff comparing two MySQL databases. See the
[example.diff](./example.diff) file in this repository.

#### Dependencies

* Python 3.x
* [MySQL connector for Python](http://dev.mysql.com/downloads/connector/python/)

#### Usage

	usage: mysqldiff.py [-h] -old OLDDB -new NEWDB [-out OUTFILE]

	arguments:
		-h, --help    show this help message and exit
		-old OLDDB    the connection to the old database
		-new NEWDB    the connection to the new database
		-out OUTFILE  a path to the output file

The connection string should have the following format:

	host:port/database?user=user&password=password
	
Everything except the database name is optional with the following default values:

	host:		localhost
	port:		3306
	user:		root
	password:	<none>

Thus, you can use the script in the following way:

	python mysqldiff.py -old <old_db_name> -new <new_db_name> -out <outputfile.diff>