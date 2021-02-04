import socket
import time
import struct
import binascii
import math
import threading
import os
import random
from colorama import Fore, init


# region HELP FUNCTIONS
init(autoreset=True)


def clear_console():
    _ = os.system('cls')


def size_of_data(data_len, data_type, num_of_fragments):
    print(f"Number of fragments: {num_of_fragments}")
    if data_len / 1048576 > 1:
        print(f"Size of {data_type}: {round(data_len / 1048576, 3)} MB")
    elif data_len / 1024 > 1:
        print(f"Size of {data_type}: {round(data_len / 1024, 3)} KB")
    else:
        print(f"Size of {data_type}: {data_len} B")
# endregion


# region CLIENT

correctly_sent = 0  # number of correctly sent fragments
end_event = threading.Event()  # set if connection ended
change_event = threading.Event()  # set if changing from client to server
fragments = {}  # fragments which are currently sent
all_fragments = 0


# function used to listen everything, that is sent by server to client (used in multithreading)
def listener(client_socket, server_addr):
    global correctly_sent
    global all_fragments
    first = True
    while True:
        try:
            data = client_socket.recv(1500)
            option = struct.unpack("b", data[:1])[0]
            if option == 1:  # fragment received correctly
                correctly_sent += 1
                client_socket.settimeout(15)
            elif option == 2:  # keep alive received
                first = True
                client_socket.settimeout(15)
                print(Fore.GREEN + "Keeping connection alive")
            elif option == 3 or option == 4:
                client_socket.settimeout(None)
            elif option == 5:  # fragment received damaged
                order = struct.unpack("i", data[1:])[0]
                fragment = fragments[order]
                crc = binascii.crc_hqx(fragment, 0xffff)
                fragment = struct.pack("b", 7) + struct.pack("iH", order, crc) + fragment
                client_socket.sendto(fragment, server_addr)
                all_fragments += 7
                print(f"{order}. fragment sent. Size of fragment: {len(fragment)} B")
                client_socket.settimeout(15)
            elif option == 6:  # end of communication received
                print(Fore.GREEN + "Ending connection...")
                end_event.set()
                return
        except socket.timeout:  # socket run out of keep alive time
            if change_event.isSet():
                return
            if first:
                client_socket.sendto(struct.pack("b", 2), server_addr)
                all_fragments += 1
                first = False
            else:
                end_event.set()
                print(Fore.GREEN + "Time from keep alive has run out.")
                return
        except ConnectionResetError:  # server down, end of communication
            end_event.set()
            print(Fore.GREEN + "Server down.")
            return


# function to fraction data into fragments
def fragment_data(fragmentation, num_of_fragments, data):
    global fragments
    prev_frag = 0
    curr_frag = fragmentation
    fragments = {}
    for i in range(num_of_fragments):
        fragments[i] = data[prev_frag:curr_frag]
        prev_frag += fragmentation
        curr_frag += fragmentation


# function to send text to server
def send_text(client_socket, server_addr):
    global all_fragments
    info = struct.pack("b", 3)
    client_socket.sendto(info, server_addr)
    all_fragments += 1

    print("Simulate damaged fragment: y/n")
    error = input("Your choice: ")
    fragmentation = int(input("Fragment size: "))
    while not 0 < fragmentation <= 1465:
        print("Wrong size. Try it again.")
        fragmentation = int(input("Fragment size: "))
    message = input("Write message: ")

    message = message.encode()
    num_of_fragments = math.ceil(len(message) / fragmentation)
    fragment_data(fragmentation, num_of_fragments, message)

    info = struct.pack("b", 3) + struct.pack("i", num_of_fragments)
    client_socket.sendto(info, server_addr)  # sending info packet with info that text is sent
    all_fragments += 5

    error_num = random.randint(0, num_of_fragments)
    for i in range(num_of_fragments):  # cycle of sending fragments
        time.sleep(0.00005)
        msg = fragments[i]
        crc = binascii.crc_hqx(msg, 0xffff)
        if i == error_num and error == "y":
            crc += 1
        msg = struct.pack("b", 7) + struct.pack("iH", i, crc) + msg
        client_socket.sendto(msg, server_addr)
        all_fragments += 7
        print(f"{i}. fragment sent. Size of fragment: {len(msg)} B")

    while correctly_sent < num_of_fragments:
        pass  # cycle that run until everything is received by server correctly

    print(Fore.GREEN + "Message sent")
    size_of_data(len(message), "message", num_of_fragments)
    print(f"Réžia: {all_fragments} B")


# function to send file to server
def send_file(client_socket, server_addr):
    global all_fragments
    info = struct.pack("b", 4)
    client_socket.sendto(info, server_addr)
    all_fragments += 1

    print("Simulate damaged fragment: y/n")
    error = input("Your choice: ")

    file_name = input("File name: ")
    file = open(file_name, "rb")
    bin_file = file.read()
    fragmentation = int(input("Fragment size: "))
    while not 0 < fragmentation <= 1465:
        print("Wrong fragment size. Try it again.")
        fragmentation = int(input("Fragment size: "))

    num_of_fragments = math.ceil(len(bin_file) / fragmentation)
    fragment_data(fragmentation, num_of_fragments, bin_file)
    info = struct.pack("b", 4) + struct.pack("i", num_of_fragments) + file_name.encode()
    client_socket.sendto(info, server_addr)  # sending info packet with info that file is sent
    all_fragments += 5 + len(file_name.encode())

    error_num = random.randint(0, num_of_fragments)
    for i in range(num_of_fragments):  # cycle of sending file
        time.sleep(0.00005)
        fragment = fragments[i]
        crc = binascii.crc_hqx(fragment, 0xffff)
        if i == error_num and error == "y":
            crc += 1
        fragment = struct.pack("b", 7) + struct.pack("iH", i, crc) + fragment
        client_socket.sendto(fragment, server_addr)
        all_fragments += 7
        print(f"{i}. fragment sent. Size of fragment: {len(fragment)} B")

    while correctly_sent < num_of_fragments:
        pass  # cycle that run until everything is received by server correctly

    print(Fore.GREEN + "Everything sent")
    print(Fore.GREEN + "Path to file, which was sent: " + Fore.RESET + os.path.abspath(file_name))
    size_of_data(len(bin_file), "file", num_of_fragments)
    file.close()
    print(f"Réžia: {all_fragments} B")


# menu for client
def client_choices(client_socket, server_addr):
    global correctly_sent
    global change_event
    global all_fragments
    change_event.clear()
    end_event.clear()
    thread_listener = threading.Thread(target=listener, args=(client_socket, server_addr), daemon=True)
    thread_listener.name = "listener"
    thread_listener.start()

    while True:

        options = ["m", "f", "e", "g", ""]
        print("Press \"m\" to send message\nPress \"f\" to send file\nPress \"g\" to change "
              "to server\nPress \"e\" to end connection\nPress \"Enter\" to update")
        option = input("Your option: ")

        while option not in options:
            print("Try it again.")
            print("Press \"m\" to send message\nPress \"f\" to send file\nPress \"g\" to change "
                  "to server\nPress \"e\" to end connection\nPress \"Enter\" to update")
            option = input("Your option: ")

        if end_event.isSet():  # end of communication
            thread_listener.join()
            client_socket.close()
            print(Fore.GREEN + "Connection ended.")
            return

        if option == "m":  # want to send message
            correctly_sent = 0
            print(Fore.GREEN + "Sending message")
            send_text(client_socket, server_addr)
        elif option == "f":  # want to send file
            correctly_sent = 0
            print(Fore.GREEN + "Sending file")
            send_file(client_socket, server_addr)
        elif option == "g":  # change to server
            print(Fore.GREEN + "Changing to server...")
            change_event.set()
            end_event.set()
            thread_listener.join()
            clear_console()
            print(Fore.GREEN + "Changed to server")
            all_fragments = 0
            info_receiving(client_socket, server_addr)
            return
        elif option == "e":  # end of communication
            end_event.set()
            data = struct.pack("b", 6)
            client_socket.sendto(data, server_addr)
            all_fragments += 1
            thread_listener.join()
            client_socket.close()
            print(Fore.GREEN + "Connection ended.")
            return


# initialization function for client
def client():
    global all_fragments
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    host = input("IP address: ")
    port = int(input("Port: "))
    server_addr = (host, port)

    info = struct.pack("b", 0)  # initialization message
    client_socket.sendto(info, server_addr)
    all_fragments += 1
    try:
        client_socket.settimeout(30)
        while True:
            msg = client_socket.recv(1500)
            if struct.unpack("b", msg[:1])[0] == 0:
                client_socket.settimeout(None)
                print(Fore.GREEN + "Connected to server")
                client_choices(client_socket, server_addr)
                break
    except socket.timeout:
        data = struct.pack("b", 6)
        client_socket.sendto(data, server_addr)
        all_fragments += 1
        print(Fore.GREEN + "Time to connect run out")


# endregion


# region SERVER

correctly_received = 0  # number of correctly received fragments


# function to save file (used in multithreading)
def save_file(info, num_of_fragments, fragmented_file):
    if not os.path.exists('Received files'):
        os.makedirs('Received files')

    file_name = 'Received files\\' + info[5:].decode()
    new_file_name = file_name
    counter = 1
    name = file_name.split(".")
    while True:
        if os.path.isfile(new_file_name):
            new_file_name = f"{name[0]}_{str(counter)}.{name[1]}"
            counter += 1
        else:
            break

    file = open(new_file_name, "wb")
    print(Fore.GREEN + "Saving file...")
    bin_file = b""
    for i in range(num_of_fragments):
        bin_file += fragmented_file[i]

    file.write(bin_file)
    print(Fore.GREEN + "File is saved there: " + Fore.RESET + os.path.abspath(new_file_name))
    file.close()


# function for receiving text
def text_receiving(server_socket, client_addr):
    global correctly_received
    correctly_received = 0
    info = server_socket.recv(1500)
    num_of_fragments = struct.unpack("i", info[1:])[0]
    full_msg = {}
    fragments_received = [False for _ in range(num_of_fragments)]

    while correctly_received < num_of_fragments:
        try:
            server_socket.settimeout(1)
            msg = server_socket.recv(1500)
            option = struct.unpack("b", msg[:1])[0]
            if option == 7:  # data packet received
                order, crc = struct.unpack("iH", msg[1:7])
                if crc == binascii.crc_hqx(msg[7:], 0xffff):  # correct fragment received
                    print(f"{order}. fragment received CORRECTLY. Size of fragment {len(msg)} B")
                    data = struct.pack("b", 1) + struct.pack("i", order)
                    server_socket.sendto(data, client_addr)
                    full_msg[order] = msg[7:]
                    fragments_received[order] = True
                    correctly_received += 1
                else:  # damaged fragment received
                    print(f"{order}. fragment received DAMAGED. Size of fragment {len(msg)} B")
                    data = struct.pack("b", 5) + struct.pack("i", order)
                    server_socket.sendto(data, client_addr)
        except socket.timeout:
            for i in range(num_of_fragments):  # cycle that ask to send again fragments that weren't received
                if not fragments_received[i]:
                    print(f"{i}. fragment NOT received. Request sent")
                    data = struct.pack("b", 5) + struct.pack("i", i)
                    server_socket.sendto(data, client_addr)

    message = b""
    for i in range(num_of_fragments):
        message += full_msg[i]

    size_of_data(len(message), "message", num_of_fragments)
    print(Fore.GREEN + "Message:")
    print(message.decode())


# function for receiving file
def file_receiving(server_socket, client_addr):
    global correctly_received
    correctly_received = 0
    fragmented_file = {}

    info = server_socket.recv(1500)
    num_of_fragments = struct.unpack("i", info[1:5])[0]
    fragments_received = [False for _ in range(num_of_fragments)]
    size = 0

    while correctly_received < num_of_fragments:
        try:
            server_socket.settimeout(1)
            fragment = server_socket.recv(1500)
            option = struct.unpack("b", fragment[:1])[0]
            if option == 7:  # data packet received
                order, crc = struct.unpack("iH", fragment[1:7])
                if crc == binascii.crc_hqx(fragment[7:], 0xffff):  # correct fragment received
                    print(f"{order}. fragment received CORRECTLY. Size of fragment {len(fragment)} B")
                    data = struct.pack("b", 1) + struct.pack("i", order)
                    server_socket.sendto(data, client_addr)
                    fragmented_file[order] = fragment[7:]
                    size += len(fragment[7:])
                    fragments_received[order] = True
                    correctly_received += 1
                else:  # damaged fragment received
                    print(f"{order}. fragment received DAMAGED. Size of fragment {len(fragment)} B")
                    data = struct.pack("b", 5) + struct.pack("i", order)
                    server_socket.sendto(data, client_addr)
        except socket.timeout:  # cycle that ask to send again fragments that weren't received
            for i in range(num_of_fragments):
                if not fragments_received[i]:
                    print(f"{i}. fragment NOT received. Request sent")
                    data = struct.pack("b", 5) + struct.pack("i", i)
                    server_socket.sendto(data, client_addr)

    size_of_data(size, "file", num_of_fragments)

    thread = threading.Thread(target=save_file, args=(info, num_of_fragments, fragmented_file))
    thread.start()  # start thread, that save file
    time.sleep(1)
    return thread


# menu fo server
def server_choices():
    options = ["c", "e", "g"]
    print("Press \"c\" to continue as server\nPress \"e\" to end connection\nPress \"g\" to change to client")
    option = input("Your option: ")

    while option not in options:
        print("Try it again.")
        print("Press \"c\" to continue as server\nPress \"e\" to end connection\nPress \"g\" to change to client")
        option = input("Your option: ")

    return option


# function, that receive packets from client
def info_receiving(server_socket, client_addr):
    thread = None
    server_socket.settimeout(None)
    try:
        while True:
            print(Fore.GREEN + "Waiting for packet")
            info = server_socket.recv(1500)
            option = struct.unpack("b", info[:1])[0]

            if option == 2:  # keep alive received
                print(Fore.GREEN + "Keep alive received")
                data = struct.pack("b", 2)
                server_socket.settimeout(30)
                server_socket.sendto(data, client_addr)
            elif option == 3:  # message is going to be received
                print(Fore.GREEN + "Receiving message")
                server_socket.settimeout(None)
                server_socket.sendto(info, client_addr)
                text_receiving(server_socket, client_addr)
                option = server_choices()
                server_socket.settimeout(30)
            elif option == 4:  # file is going to be received
                print(Fore.GREEN + "Receiving file")
                server_socket.settimeout(None)
                server_socket.sendto(info, client_addr)
                thread = file_receiving(server_socket, client_addr)
                option = server_choices()
                server_socket.settimeout(30)
            elif option == 6:  # end of communication received
                server_socket.settimeout(None)
                data = struct.pack("b", 6)
                server_socket.sendto(data, client_addr)
                server_socket.close()
                print(Fore.GREEN + "Connection ended by client")
                if thread and thread.is_alive():
                    print(Fore.GREEN + "Waiting for file to be saved...")
                    thread.join()
                return

            if option == "e":  # end of communication by server
                server_socket.settimeout(None)
                data = struct.pack("b", 6)
                server_socket.sendto(data, client_addr)
                server_socket.close()
                if thread and thread.is_alive():
                    print(Fore.GREEN + "Waiting for file to be saved...")
                    thread.join()
                print(Fore.GREEN + "Connection ended")
                return
            elif option == "g":  # change to client
                server_socket.settimeout(None)
                if thread and thread.is_alive():
                    print(Fore.GREEN + "Waiting for file to be saved...")
                    thread.join()
                clear_console()
                print(Fore.GREEN + "Changed to client")
                client_choices(server_socket, client_addr)
                return

    except socket.timeout:
        server_socket.close()
        print(Fore.GREEN + "Time from keep alive has run out.")
    except ConnectionResetError:
        server_socket.close()
        print(Fore.GREEN + "Time from keep alive has run out.")


# initialization function for server
def server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    port = int(input("Port: "))
    server_socket.bind(("", port))
    print(Fore.GREEN + "Waiting for someone to connect")
    info, client_addr = server_socket.recvfrom(1500)
    option = struct.unpack("b", info[:1])[0]
    if option == 0:
        print(Fore.GREEN + "Connection created with client")
        server_socket.sendto(info, client_addr)
        info_receiving(server_socket, client_addr)


# endregion


# region MAIN

def main():
    print("s → for Server\nc → for client")
    option = input("Your option: ")

    if option == "c":
        client()
    elif option == "s":
        server()


# endregion


main()
