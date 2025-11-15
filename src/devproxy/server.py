import asyncio

async def handle_client(reader, writer):
    """Handle One client connection. Read request, send response, clean up.
    This is wrapped in try/except so one bad client can't crash the server"""
    client_addr = writer.get_extra_info("peername")
    print(f"Client Connected:{client_addr}")
    try: 
    # Read the http request line
        print("Starting request processing...")
        request_line_bytes = await reader.readline()
        if not request_line_bytes:
            print("Client disconnected without sending data")
            return
    # Convert bytes to string and remove the \r\n
        request_line = request_line_bytes.decode('utf-8').strip()
    # print("Client connected!")
        print(f"Got Request: {request_line}")
        # Read Headers
        headers = {}
        while True:
            header_line_bytes = await reader.readline()
            if not header_line_bytes:
                print("Client disconnected mid-headers")
                return
            header_line = header_line_bytes.decode('utf-8').strip()
        
            if header_line == "":
                print("End of Headers")
                break
            # Malformed header protection
            if ": " not in header_line:
                print(f"Bad header format: {header_line}")
                continue

            key, value = header_line.split(": ", 1)
            headers[key] = value
            print(f" {key}: {value}")
        print(f"All Headers: {headers}")

        #Read Body 
        body = b""
        if "Content-Length" in headers:
            try:
                content_length = int(headers["Content-Length"])
                print(f"Body length: {content_length} bytes")

                body = await reader.readexactly(content_length)
                print(f"Body: {body.decode('utf-8')[:100]}...")

            except ValueError:
                print(f"Invalid Content-Lenght: {headers['Content-Lenght']}")
                body = b""
            except asyncio.IncompleteReadError:
                print("Client Disconnected before sending full body")
                body = b""
        # Send Response
        response_body = f"Hello, From DevProxy! You requested: {request_line}".encode()

        #Build Proper HTTP Response
        response = (b"HTTP/1.1 200 OK\r\n"
                    b"Content-Lenght: text/plain\r\n"
                    b"\r\n"
                    +response_body 
        )
        writer.write(response)
        await writer.drain()
        print("Response sent")
    except Exception as e:
        print(f" Error handling client: {e}")

    finally:
        print(f" Disconnecting: {client_addr}")      
    writer.close()
    await writer.wait_closed()


async def main(): 
    server = await asyncio.start_server(handle_client, "localhost", 8888)
    addr = server.sockets[0].getsockname()
    print(f"Serving on {addr}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__": 
    asyncio.run(main())

