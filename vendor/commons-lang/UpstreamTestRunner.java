/* Licensed under the Apache License, Version 2.0. See the upstream LICENSE.txt. */
import java.io.PrintWriter;
import java.io.StringWriter;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import junit.framework.AssertionFailedError;
import junit.framework.Test;
import junit.framework.TestCase;
import junit.framework.TestListener;
import junit.framework.TestResult;
import junit.framework.TestSuite;

/** Records unchanged upstream JUnit 3 tests without requiring legacy Maven plugins. */
public final class UpstreamTestRunner implements TestListener {
    private static final class Case {
        final String name;
        Throwable problem;
        String kind;
        Case(String name) { this.name = name; }
    }
    private final List<Case> cases = new ArrayList<Case>();
    private final Map<Test, Case> active = new IdentityHashMap<Test, Case>();
    public void startTest(Test test) {
        Case value = new Case(test.toString());
        cases.add(value);
        active.put(test, value);
    }
    public void endTest(Test test) { active.remove(test); }
    public void addError(Test test, Throwable problem) { record(test, problem, "error"); }
    public void addFailure(Test test, AssertionFailedError problem) { record(test, problem, "failure"); }
    private void record(Test test, Throwable problem, String kind) {
        Case value = active.get(test);
        value.problem = problem;
        value.kind = kind;
    }
    private static String escape(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    .replace("\"", "&quot;").replace("'", "&apos;");
    }
    private static Test stableOrder(Test test) {
        if (!(test instanceof TestSuite)) { return test; }
        TestSuite original = (TestSuite) test;
        List<Test> children = new ArrayList<Test>();
        for (int i = 0; i < original.testCount(); i++) {
            children.add(stableOrder(original.testAt(i)));
        }
        Collections.sort(children, new Comparator<Test>() {
            public int compare(Test a, Test b) { return a.toString().compareTo(b.toString()); }
        });
        TestSuite sorted = new TestSuite(original.getName());
        for (Test child : children) { sorted.addTest(child); }
        return sorted;
    }
    public static void main(String[] args) throws Exception {
        TestSuite suite = new TestSuite("Commons Lang 2.6 unchanged upstream tests");
        if (args[0].equals("regression")) {
            Class<?> type = Class.forName("org.apache.commons.lang.ClassUtilsTest");
            suite.addTest((Test) type.getConstructor(String.class).newInstance("testGetClassSOE"));
        } else if (args[0].equals("classutils")) {
            suite.addTest(new TestSuite(Class.forName("org.apache.commons.lang.ClassUtilsTest")));
        } else {
            for (String name : Files.readAllLines(Paths.get(args[1]), StandardCharsets.UTF_8)) {
                Class<?> type = Class.forName(name);
                if (Modifier.isAbstract(type.getModifiers())) {
                    System.out.println("DISCOVERY abstract class: " + name);
                    continue;
                }
                try {
                    Method factory = type.getMethod("suite");
                    if (Modifier.isStatic(factory.getModifiers()) && Test.class.isAssignableFrom(factory.getReturnType())) {
                        suite.addTest((Test) factory.invoke(null));
                    } else {
                        throw new IllegalStateException("Unsupported suite factory: " + name);
                    }
                } catch (NoSuchMethodException missing) {
                    if (!TestCase.class.isAssignableFrom(type)) {
                        throw new IllegalStateException("Not a JUnit 3 test: " + name);
                    }
                    suite.addTest(new TestSuite(type));
                }
            }
        }
        UpstreamTestRunner listener = new UpstreamTestRunner();
        TestResult result = new TestResult();
        result.addListener(listener);
        stableOrder(suite).run(result);
        try (PrintWriter output = new PrintWriter(args[2], "UTF-8")) {
            output.println("<?xml version=\"1.0\" encoding=\"UTF-8\"?>");
            output.println("<testsuite name=\"commons-lang-2.6\" tests=\"" + result.runCount()
                + "\" failures=\"" + result.failureCount() + "\" errors=\"" + result.errorCount() + "\" skipped=\"0\">");
            for (Case value : listener.cases) {
                output.println("<testcase name=\"" + escape(value.name) + "\">");
                if (value.problem != null) {
                    StringWriter trace = new StringWriter();
                    value.problem.printStackTrace(new PrintWriter(trace));
                    output.println("<" + value.kind + " type=\"" + escape(value.problem.getClass().getName()) + "\">"
                        + escape(trace.toString()) + "</" + value.kind + ">");
                }
                output.println("</testcase>");
            }
            output.println("</testsuite>");
        }
        System.out.println("Tests=" + result.runCount() + " failures=" + result.failureCount() + " errors=" + result.errorCount());
        System.exit(result.wasSuccessful() ? 0 : 1);
    }
}
