import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.IntWritable;
import org.apache.hadoop.io.SequenceFile;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.shaded.com.fasterxml.jackson.core.JsonFactory;
import org.apache.hadoop.shaded.com.fasterxml.jackson.core.JsonParser;
import org.apache.hadoop.shaded.com.fasterxml.jackson.core.JsonToken;
import org.apache.hadoop.shaded.com.fasterxml.jackson.core.StreamReadConstraints;
import org.apache.hadoop.shaded.com.fasterxml.jackson.core.async.ByteArrayFeeder;
import org.apache.hadoop.shaded.com.fasterxml.jackson.core.exc.StreamConstraintsException;
import org.apache.hadoop.shaded.com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.hadoop.shaded.org.apache.commons.configuration2.AbstractYAMLBasedConfiguration;
import org.apache.hadoop.shaded.org.jline.reader.LineReaderBuilder;
import org.apache.hadoop.shaded.org.jline.terminal.Terminal;
import org.apache.hadoop.shaded.org.jline.terminal.TerminalBuilder;

/** Bounded checks of the actual shaded runtime; no server or network traffic. */
public final class ComponentSmoke {
  private static final class ParsedYaml extends AbstractYAMLBasedConfiguration {
    void loadMap(Map<String, Object> value) { load(value); }
  }

  public static void main(String[] args) throws Exception {
    Configuration conf = new Configuration();
    conf.set("fs.defaultFS", "file:///");
    conf.set("hadoop.tmp.dir", "/tmp/hadoop-component");
    java.nio.file.Path dir = Files.createTempDirectory("hadoop-component-");
    Path path = new Path(dir.resolve("sample.seq").toUri());
    try (FileSystem fs = FileSystem.newInstanceLocal(conf)) {
      try (SequenceFile.Writer writer = SequenceFile.createWriter(conf,
          SequenceFile.Writer.file(path), SequenceFile.Writer.keyClass(IntWritable.class),
          SequenceFile.Writer.valueClass(Text.class))) {
        writer.append(new IntWritable(7), new Text("pipeline"));
      }
      try (SequenceFile.Reader reader = new SequenceFile.Reader(conf, SequenceFile.Reader.file(path))) {
        IntWritable key = new IntWritable();
        Text value = new Text();
        if (!reader.next(key, value) || key.get() != 7 || !value.toString().equals("pipeline")
            || reader.next(key, value)) throw new AssertionError("SequenceFile round-trip failed");
      }
      if (!fs.delete(new Path(dir.toUri()), true)) throw new AssertionError("Local FS cleanup failed");
    }

    ObjectMapper mapper = new ObjectMapper();
    if (!mapper.version().toString().equals("2.18.11")) throw new AssertionError(mapper.version());
    if (mapper.readTree("{\"net\":77}").path("net").asInt() != 77) throw new AssertionError("JSON failed");

    JsonFactory factory = JsonFactory.builder().streamReadConstraints(
        StreamReadConstraints.builder().maxNumberLength(10).build()).build();
    byte[] number = "[1234567890123456789012345678901234567890]".getBytes(StandardCharsets.US_ASCII);
    boolean rejected = false;
    try (JsonParser parser = factory.createNonBlockingByteArrayParser()) {
      ByteArrayFeeder feeder = (ByteArrayFeeder) parser.getNonBlockingInputFeeder();
      try {
        for (int i = 0; i < number.length; i++) {
          feeder.feedInput(number, i, i + 1);
          while (parser.nextToken() != JsonToken.NOT_AVAILABLE) { }
        }
        feeder.endOfInput();
        while (parser.nextToken() != null) { }
      } catch (StreamConstraintsException expected) {
        rejected = true;
      }
    }
    if (!rejected) throw new AssertionError("Chunked numeric input bypassed maxNumberLength");

    ParsedYaml yaml = new ParsedYaml();
    yaml.loadMap(Map.of("batch", 7));
    if (yaml.getInt("batch") != 7) throw new AssertionError("YAML load failed");
    Map<String, Object> cycle = new HashMap<>();
    cycle.put("recursive", cycle);
    cycle.put("batch", 7);
    yaml.loadMap(cycle);
    if (yaml.getInt("batch") != 7) throw new AssertionError("Cyclic YAML hierarchy was not bounded");

    try (Terminal terminal = TerminalBuilder.builder().system(false).dumb(true)
        .streams(new ByteArrayInputStream("local-batch\n".getBytes(StandardCharsets.UTF_8)),
                 new ByteArrayOutputStream()).build()) {
      String line = LineReaderBuilder.builder().terminal(terminal).build().readLine();
      if (!line.equals("local-batch")) throw new AssertionError("JLine read failed");
    }
    try {
      Class.forName("org.apache.hadoop.shaded.org.eclipse.jetty.http.HttpURI");
      throw new AssertionError("Excluded Jetty component is still present");
    } catch (ClassNotFoundException expected) { }
    System.out.println("PASS local-fs sequence-file jackson-roundtrip jackson-chunk-budget yaml-hierarchy-normal yaml-hierarchy-cycle jline-dumb jetty-absent");
  }
}
