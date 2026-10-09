package fedora.server.utilities;

import java.io.ByteArrayInputStream;

import org.junit.Test;


public class DCFieldsTest {
    private final static String dcWithXmlLang; 

    static {
        StringBuilder sb = new StringBuilder();
        sb.append("<oai_dc:dc xmlns:oai_dc=\"http://www.openarchives.org/OAI/2.0/oai_dc/\" ");
        sb.append("    xmlns:dc=\"http://purl.org/dc/elements/1.1/\">");
        sb.append("<dc:subject xml:lang=\"da\">Tidsinterval</dc:subject>");
        sb.append("<dc:subject xml:lang=\"en\">Time interval</dc:subject>");
        sb.append("<dc:subject>interval</dc:subject>");
        sb.append("</oai_dc:dc> ");
        dcWithXmlLang = sb.toString();
    }

    @Test
    public void testDCFieldsInputStream() throws Exception {
        DCFields dc = new DCFields(new ByteArrayInputStream(dcWithXmlLang.getBytes("UTF-8")));
        System.out.println(dc.getAsXML());
    }

}

 	  	 
