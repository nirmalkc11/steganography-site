from stego import embed_message, extract_message


def main():
    carrier_file = "uploads/input.jpg"
    secret_file = "hidden_messages/secret.txt"
    stego_file = "generated/output_stego.jpg"
    recovered_base = "generated/recovered_secret"

    S = 8192
    L = 64
    mode = "fixed"

    print("Embedding message...")
    embed_message(
        carrier_path=carrier_file,
        message_path=secret_file,
        output_path=stego_file,
        S=S,
        L=L,
        mode=mode
    )
    print(f"Stego file created: {stego_file}")

    print("Extracting message...")
    recovered_file = extract_message(
        stego_path=stego_file,
        output_base_path=recovered_base,
        S=S,
        L=L,
        mode=mode
    )
    print(f"Recovered message created: {recovered_file}")

    with open(secret_file, "rb") as f1, open(recovered_file, "rb") as f2:
        if f1.read() == f2.read():
            print("Success: recovered message matches the original.")
        else:
            print("Mismatch: recovered message does not match the original.")


if __name__ == "__main__":
    main()