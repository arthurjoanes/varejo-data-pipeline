/* SPDX-License-Identifier: MIT */
import shaded.parquet.com.fasterxml.jackson.core.JsonFactory;
import shaded.parquet.com.fasterxml.jackson.core.StreamReadConstraints;
import shaded.parquet.com.fasterxml.jackson.core.exc.StreamConstraintsException;
import shaded.parquet.com.fasterxml.jackson.databind.ObjectMapper;

/** Tests the relocated classes in the produced JAR, rather than an external Jackson classpath. */
public final class JacksonComponentCheck {
    public static void main(String[] args) throws Exception {
        JsonFactory factory = JsonFactory.builder().streamReadConstraints(
            StreamReadConstraints.builder().maxNumberLength(128).maxNestingDepth(16).build()
        ).build();
        ObjectMapper mapper = new ObjectMapper(factory);
        if (!"2.22.3".equals(factory.version().toString())
                || !"2.22.3".equals(mapper.version().toString())) {
            throw new AssertionError("Unexpected relocated Jackson versions");
        }
        String json = "{\"ok\":[1,\"value\"],\"amount\":12.5}";
        if (!json.equals(mapper.writeValueAsString(mapper.readTree(json)))) {
            throw new AssertionError("Relocated JSON roundtrip differs");
        }
        for (String hostile : new String[] {"1".repeat(100_000), "[".repeat(100) + "0" + "]".repeat(100)}) {
            try {
                mapper.readTree(hostile);
                throw new AssertionError("Expected bounded parser rejection");
            } catch (StreamConstraintsException expected) {
                // These resource-limit checks do not reproduce every listed advisory.
            }
        }
        System.out.println("Relocated Jackson 2.22.3: versions, JSON roundtrip, number/depth bounds passed");
    }
}
