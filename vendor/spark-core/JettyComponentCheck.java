// SPDX-License-Identifier: Apache-2.0
// URI regression cases follow Jetty commit 82969c77f6da46e27008b10b3c14840cd31db084.
// These checks load the shaded classes from the actual Spark core candidate.
import org.sparkproject.jetty.http.HttpURI;
import org.sparkproject.jetty.server.Handler;
import org.sparkproject.jetty.server.LocalConnector;
import org.sparkproject.jetty.server.Request;
import org.sparkproject.jetty.server.Response;
import org.sparkproject.jetty.server.Server;
import org.sparkproject.jetty.util.Callback;

public final class JettyComponentCheck {
    private static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        boolean patched = Boolean.parseBoolean(args[0]);
        String[][] cases = {
            {"/path;/./info", "/path/info"},
            {"/path;/../info", "/info"},
            {"//host/path;/../info", "/info"}
        };
        int correct = 0;
        for (String[] item : cases) {
            if (item[1].equals(HttpURI.from(item[0]).getCanonicalPath())) correct++;
        }
        if (!patched) {
            require(correct < cases.length, "Original runtime unexpectedly passes the regression control");
            System.out.println("{\"baseline_regression_detected\":true,\"uri_cases_correct\":" + correct + "}");
            return;
        }
        require(correct == cases.length, "Matrix parameters must not bypass path canonicalization");
        Server server = new Server();
        LocalConnector connector = new LocalConnector(server);
        server.addConnector(connector);
        server.setHandler(new Handler.Abstract() {
            @Override
            public boolean handle(Request request, Response response, Callback callback) {
                response.setStatus(200);
                callback.succeeded();
                return true;
            }
        });
        try {
            server.start();
            String valid = connector.getResponse("GET / HTTP/1.1\r\nHost: local\r\nConnection: close\r\n\r\n");
            require(valid.startsWith("HTTP/1.1 200"), "Valid in-memory request must succeed");
            String mismatch = connector.getResponse("GET http://other/ HTTP/1.1\r\nHost: local\r\nConnection: close\r\n\r\n");
            require(mismatch.startsWith("HTTP/1.1 400"), "Authority mismatch must be rejected");
            String userInfo = connector.getResponse("GET http://user:password@local/ HTTP/1.1\r\nHost: local\r\nConnection: close\r\n\r\n");
            require(userInfo.startsWith("HTTP/1.1 400"), "Deprecated user-info authority must be rejected");
        } finally {
            server.stop();
            server.destroy();
        }
        System.out.println("{\"uri_regressions\":3,\"in_memory_http_cases\":3,\"network_listener\":false,\"result\":\"passed\"}");
    }
}
