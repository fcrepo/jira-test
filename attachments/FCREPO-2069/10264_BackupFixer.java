import java.io.File;
import java.io.FileInputStream;
import java.util.zip.GZIPInputStream;
import java.io.InputStreamReader;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.zip.GZIPOutputStream;
import java.io.FileOutputStream;
import java.util.HashSet;
import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonToken;


public class BackupFixer {

    public static void main( String[] args ) throws IOException {
        if ( args.length < 1 ) {
            System.err.println("usage: BackupFixer [backup directory]");
            return;
        }

        File dir = new File(args[0]);

        if ( !dir.exists() || dir.listFiles().length == 0 ) {
            System.err.println("Directory " + args[0] + " is empty or doesn't exist");
            return;
        }

        File[] files = dir.listFiles();
        for ( int i = 0; i < files.length; i++ ) {
            String fn = files[i].getName();
            if ( files[i].isFile() && fn.startsWith("documents_") && fn.endsWith(".gz") ) {
                fix(files[i]);
            }
        }
    }
    private static void fix(File f) throws IOException {
        System.out.println("Fixing: " + f.getName());

        // move original file
        File moved = new File(f.getParent(), f.getName() + ".orig");
        if ( moved.exists() ) {
           System.err.println("Backup file already exists, skipping: " + moved.getName());
           return;
        }
        f.renameTo(moved);

        // filter duplicate ids
        PrintWriter out = null;
        try {
            BufferedReader buf = new BufferedReader(new InputStreamReader(new GZIPInputStream(
                new FileInputStream(moved))));
            out = new PrintWriter(new GZIPOutputStream(new FileOutputStream(f)));

            HashSet<String> ids = new HashSet<String>();
            for ( String line = null; (line = buf.readLine()) != null; ) {
                String id = idFromJSON(line);
                if ( id == null ) {
                    System.err.println("Unable to parse id: " + line);
                } else if ( ids.contains(id) ) {
                    System.err.println("Skipping duplicate id: " + line);
                } else {
                    ids.add(id);
                    out.println(line);
                }
            }
        } finally {
            out.close();
        }
    }
    private static String idFromJSON(String s) {
        try {
            JsonParser parser = new JsonFactory().createParser(s);
            boolean metadata = false;
            while( parser.nextToken() != JsonToken.END_OBJECT ) {
                if ( "metadata".equals(parser.getCurrentName()) ) {
                    metadata = true;
                }
                else if ( metadata && parser.getCurrentName().equals("id") ) {
                    parser.nextToken();
                    return parser.getText();
                }
            }
        } catch ( IOException ex ) {
            System.err.println("Exception during parsing: " + ex.toString());
        }
        return null;
    }
}
