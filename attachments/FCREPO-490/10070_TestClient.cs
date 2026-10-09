using System;

// C-Sharp FieldSearch Test for Fedora 3.2.x and 3.3
//
// Author: Chris Wilper
// Date  : 2009-11-24
//
// Purpose: To demonstrate use of Fedora's Field Search
//   queries with .NET generated classes.  These have historically
//   been problematic because of the way FieldSearch is invoked.
//   See http://fedora-commons.org/jira/browse/FCREPO-490
//   However, it appears that with Microsoft .NET 3.5, and a minor
//   change to Fedora's WSDL (which will be in the upcoming Fedora 3.3
//   release), both types of queries can work fine.
//
// Prerequisites:
//   1) A running Fedora 3.2.x or greater with demo objects installed
//   2) Microsoft .NET SDK Version 3.5 or greater
// 
// Generating and compiling the code:
//   1) Download the API WSDL from your running Fedora repository, e.g.:
//      http://localhost:8080/fedora/wsdl?api=API-A
//   2) If running Fedora 3.2.x, the WSDL needs to be fixed as follows:
//      - Go to the portType/operation with name "resumeFindObjects"
//      - Change the output element to point to
//        fedora-api:resumeFindObjectsResponse (it was previously
//        just "fedora-api:findObjectsResponse", which, if unchanged,
//        causes .NET to throw a runtime exception when an instance of
//        FedoraAPIAService is first constructed.
//   3) Generate FedoraAPIAService.cs from the wsdl:
//      - Run "wsdl APIA.wsdl" from the commandline
//   4) Edit the generated file and change the following:
//      - Change the constructor's signature from:
//        public FedoraAPIAService() {
//        to:
//        public FedoraAPIAService(string user, string pass) {
//      - Add the following line after this.Url = ... in the constructor:
//        this.Credentials = new System.Net.NetworkCredential(user, pass);
//   5) Compile the generated source file to a .dll:
//      - Run "csc /t:library FedoraAPIAService.cs"
//   6) Compile this test code as an exe, linking it to the dll:
//      - Run "csc /r:FedoraAPIAService.dll TestClient.cs"
//
// Running the test:
//   Run "TestClient.exe fedoraAdmin fedoraAdmin"
//   
//   Note: If your Fedora installation's API-A interface is not configured
//         to be protected by basic authentication, entering 
//         "bogusUser bogusPass" as the parameters should also work.

class TestClient
{
    public static void Main(string[] args)
    {

        // Create instance of FedoraAPIAService.dll
        FedoraAPIAService apia = new FedoraAPIAService(args[0], args[1]);

	// Test 1: FieldSearch Query with Conditions
	
	Console.WriteLine("-----------------------------------------");
	Console.WriteLine("Test 2: FieldSearch query with Conditions");
	Console.WriteLine("-----------------------------------------");
	
	FieldSearchQuery fsq = new FieldSearchQuery();

	Condition c = new Condition();
	c.@operator = ComparisonOperator.has;
	c.property = "label";
	c.value = "*Service*";

	FieldSearchQueryConditions conditions = new FieldSearchQueryConditions();
	conditions.condition = new Condition[] { c };
	fsq.Item = conditions;

	string[] sr = { "pid", "label" };

        Console.WriteLine("Finding objects where label contains the word 'Service'");
	FieldSearchResult fsr = apia.findObjects(sr, "5", fsq);

	int pageCount = 0;
	int resultCount = 0;
	Boolean done = false;
        while (!done) {
		pageCount++;
		Console.WriteLine("Processing results, page " + pageCount);
		foreach (ObjectFields fields in fsr.resultList) {
			resultCount++;
			Console.WriteLine(fields.pid + " - " + fields.label);
		}
		Console.WriteLine("Saw " + resultCount + " results so far");
		if (fsr.listSession == null) {
			done = true;
		} else {
			fsr = apia.resumeFindObjects(fsr.listSession.token);
	        }
	}	

	// Test 2: FieldSearch query with "Terms"
	
	Console.WriteLine("------------------------------------");
	Console.WriteLine("Test 2: FieldSearch query with Terms");
	Console.WriteLine("------------------------------------");
	
	fsq = new FieldSearchQuery();

	fsq.Item = "Model";

        Console.WriteLine("Finding objects where any field contains the word 'Model'");
	fsr = apia.findObjects(sr, "5", fsq);

	pageCount = 0;
	resultCount = 0;
	done = false;
        while (!done) {
		pageCount++;
		Console.WriteLine("Processing results, page " + pageCount);
		foreach (ObjectFields fields in fsr.resultList) {
			resultCount++;
			Console.WriteLine(fields.pid + " - " + fields.label);
		}
		Console.WriteLine("Saw " + resultCount + " results so far");
		if (fsr.listSession == null) {
			done = true;
		} else {
			fsr = apia.resumeFindObjects(fsr.listSession.token);
	        }
	}	
        Console.WriteLine("Finished");

    }
}
