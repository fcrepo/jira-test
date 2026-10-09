package rebuild;

import java.io.File;
import java.net.URLClassLoader;
import java.net.URL;
import java.lang.reflect.Array;
import java.lang.reflect.Method;

public class RebuildWrapper extends URLClassLoader {
    public RebuildWrapper(URL [] args){
        super(args);
    }
    public RebuildWrapper(URL[] args, ClassLoader parent) {
        super(args, parent);
    }
    
    public static void main( String [] args) throws Exception {
        String webInfLib = System.getProperty("fedora.web.inf.lib");
        if (webInfLib == null){
            System.err.println("fedora.web.inf.lib not defined");
            System.exit(1);
        }
        File webInfLibDir = new File(webInfLib);
        if (!webInfLibDir.exists()){
            System.err.println("path specified by fedora.web.inf.lib doesn't exist");
            System.exit(1);
        }
        if (!webInfLibDir.isDirectory()){
            System.err.println("path specified by fedora.web.inf.lib not a directory");
            System.exit(1);
        }
        String [] paths = webInfLibDir.list();
        URL[] urls = new URL[paths.length];
        for (int i = 0; i < paths.length; i++){
            urls[i] = new File(webInfLibDir,paths[i]).toURI().toURL();
        }
        RebuildWrapper loader = new RebuildWrapper(urls);
        Thread.currentThread().setContextClassLoader(loader); // necessary to find XML API libraries
        Class<?> rebuild = loader.findClass("fedora.server.utilities.rebuild.Rebuild");
        Method main = rebuild.getMethod("main",new Class<?>[]{String[].class});
        main.invoke(rebuild,new Object[]{args});
    }
}