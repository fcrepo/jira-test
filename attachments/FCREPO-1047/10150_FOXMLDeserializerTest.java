package org.fcrepo.server.serialization;

import static org.junit.Assert.assertTrue;

import java.util.Iterator;

import org.fcrepo.server.storage.translation.DOTranslationUtility;
import org.fcrepo.server.storage.translation.FOXMLDODeserializer;
import org.fcrepo.server.storage.types.BasicDigitalObject;
import org.fcrepo.server.storage.types.Datastream;
import org.junit.BeforeClass;
import org.junit.Test;


public class FOXMLDeserializerTest {
	
	@BeforeClass
	public static void initClass(){
        System.setProperty("fedora.hostname","localhost");
        System.setProperty("fedora.port","1024");
        System.setProperty("fedora.appServerContext","fedora");
	}

	@Test
	public void testDefaultChecksum() throws Exception{
		FOXMLDODeserializer deserializer=new FOXMLDODeserializer();
		BasicDigitalObject obj=new BasicDigitalObject();
		obj.setNew(true);
		Datastream.defaultChecksumType="MD5";
		Datastream.autoChecksum=true;
		deserializer.deserialize(this.getClass().getClassLoader().getResourceAsStream("ecm/dataobject1.xml"), obj, "UTF-8", DOTranslationUtility.DESERIALIZE_INSTANCE);
		for (Iterator<String> streams=obj.datastreamIdIterator();streams.hasNext();){
			String id=streams.next();
			for (Datastream version:obj.datastreams(id)){
				assertTrue(version.DSChecksumType == Datastream.getDefaultChecksumType());
				assertTrue(version.getChecksum().length() == 32);
			}
		}

		Datastream.defaultChecksumType="MD5";
		Datastream.autoChecksum=false;
		obj=new BasicDigitalObject();
		deserializer.deserialize(this.getClass().getClassLoader().getResourceAsStream("ecm/dataobject1.xml"), obj, "UTF-8", DOTranslationUtility.DESERIALIZE_INSTANCE);
		for (Iterator<String> streams=obj.datastreamIdIterator();streams.hasNext();){
			String id=streams.next();
			for (Datastream version:obj.datastreams(id)){
				assertTrue(version.DSChecksumType == Datastream.CHECKSUM_NONE);
				assertTrue(version.getChecksum().length() == 32);
			}
		}
	}
}
