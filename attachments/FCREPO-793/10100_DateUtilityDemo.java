import java.text.SimpleDateFormat;
import java.text.ParseException;
import java.util.Date;
import java.util.TimeZone;

public class DateUtilityDemo
{

    public static void main(String[] args) throws Exception
    {
        SimpleDateFormat format = new SimpleDateFormat( "yyyy-MM-dd'T'HH:mm:ss.SSS" );

        /** date string as client sends it*/
        String dateString = "2010-09-02T02:20:20.202";

        /** The date object parsed from the string*/
        Date date = format.parse( dateString );

        /** Emulation of FieldSearchSQLImpl call to parseDateStrict*/
        Date dateParsed = parseDateStrict( format.format( date ) );

        String timestring = String.format( "date: %s \ndate.getTime(): %s \nparseDateStrict( %s ) --> %s \nparsedDate.getTime(): %s", dateString, date.getTime(), format.format( date ), format.format( dateParsed ), dateParsed.getTime() );
        System.out.println( "incoming date:        " + dateString );
        System.out.println( "date.getTime():       " + date.getTime() );
        System.out.println( "parseDateStrict:      " + format.format( date ) + " --> " + format.format( dateParsed ) );
        System.out.println( "parsedDate.getTime(): " + dateParsed.getTime() );
    }

    /**
     * Attempt to parse the given string of form: yyyy-MM-dd[THH:mm:ss[.SSS][Z]]
     * as a Date.
     *
     * @param dateString the date string to parse
     * @return a Date representation of the dateString
     * @throws ParseException if dateString is null, empty or is otherwise
     * unable to be parsed.
     */
    public static Date parseDateStrict(String dateString) throws ParseException {
        if (dateString == null) {
            throw new ParseException("Argument cannot be null.", 0);
        } else if (dateString.isEmpty()) {
            throw new ParseException("Argument cannot be empty.", 0);
        } else if (dateString.endsWith(".")) {
            throw new ParseException("dateString ends with invalid character.", dateString.length() - 1);
        }
        SimpleDateFormat formatter = new SimpleDateFormat();
        formatter.setTimeZone(TimeZone.getTimeZone("UTC"));
        int length = dateString.length();
        if (dateString.startsWith("-")) {
            length--;
        }
        if (dateString.endsWith("Z")) {
            if (length == 11) {
                formatter.applyPattern("yyyy-MM-dd'Z'");
            } else if (length == 20) {
                formatter.applyPattern("yyyy-MM-dd'T'HH:mm:ss'Z'");
            } else if (length > 21 && length < 24) {
                // right-pad the milliseconds with 0s up to three places
                StringBuilder sb = new StringBuilder(dateString.substring(0, dateString.length() - 1));
                int dotIndex = sb.lastIndexOf(".");
                int endIndex = sb.length() - 1;
                int padding = 3 - (endIndex - dotIndex);
                for (int i = 0; i < padding; i++) {
                    sb.append("0");
                }
                sb.append("Z");
                dateString = sb.toString();
                formatter.applyPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'");
            } else if (length == 24) {
                formatter.applyPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'");
            }
        } else {
            if (length == 10) {
                formatter.applyPattern("yyyy-MM-dd");
            } else if (length == 19) {
                formatter.applyPattern("yyyy-MM-dd'T'HH:mm:ss");
            } else if (length > 20 && length < 23) {
                // right-pad millis with 0s
                StringBuilder sb = new StringBuilder(dateString);
                int dotIndex = sb.lastIndexOf(".");
                int endIndex = sb.length() - 1;
                int padding = 3 - (endIndex - dotIndex);
                for (int i = 0; i < padding; i++) {
                    sb.append("0");
                }
                dateString = sb.toString();
                formatter.applyPattern("yyyy-MM-dd'T'HH:mm:ss.SSS");
            } else if (length == 23) {
                formatter.applyPattern("yyyy-MM-dd'T'HH:mm:ss.SSS");
            } else if (dateString.endsWith("GMT") || dateString.endsWith("UTC")) {
                formatter.applyPattern("EEE, dd MMMM yyyyy HH:mm:ss z");
            }
        }
        return formatter.parse(dateString);
    }

}